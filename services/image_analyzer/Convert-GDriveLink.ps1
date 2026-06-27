#Requires -Version 5.1
<#
.SYNOPSIS
    Converts standard Google Drive sharing links into direct download links.

.DESCRIPTION
    Transforms various Google Drive URL formats into direct download URLs
    that can be used with wget, curl, Invoke-WebRequest, or browsers.

PS C:\Users\DavidM\DevOps Expert AI Course\FinalProject\services\image_analyzer> . .\Convert-GDriveLink.ps1
PS C:\Users\DavidM\DevOps Expert AI Course\FinalProject\services\image_analyzer> Convert-GDriveLink https://drive.google.com/file/d/1UVcccyNj2fOM9zZJ704AblCBpZ6iB-lC/view?usp=drive_link

.EXAMPLE
    Convert-GDriveLink "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view?usp=sharing"

.EXAMPLE
    Convert-GDriveLink -Url "https://drive.google.com/open?id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs" -Copy

.EXAMPLE
    @("https://drive.google.com/file/d/ABC123/view", "https://drive.google.com/open?id=DEF456") | Convert-GDriveLink
#>

function Convert-GDriveLink {
    [CmdletBinding()]
    param (
        [Parameter(Mandatory, ValueFromPipeline, ValueFromPipelineByPropertyName, Position = 0)]
        [string[]]$Url,

        [Parameter()]
        [switch]$Copy
    )

    begin {
        $results = @()
        $directBase = "https://drive.google.com/uc?export=download&id="
    }

    process {
        foreach ($link in $Url) {
            $link = $link.Trim()
            $fileId = $null

            if ($link -match '/file/d/([a-zA-Z0-9_-]+)') {
                $fileId = $Matches[1]
            }
            elseif ($link -match '[?&]id=([a-zA-Z0-9_-]+)') {
                $fileId = $Matches[1]
            }
            elseif ($link -match '/folders/([a-zA-Z0-9_-]+)') {
                $fileId = $Matches[1]
                Write-Warning "Detected a folder link. Folder downloads require authentication and may not work directly."
            }
            elseif ($link -match '^[a-zA-Z0-9_-]{25,}$') {
                $fileId = $link
                Write-Verbose "Input looks like a bare file ID - treating it as one."
            }

            if ($fileId) {
                $directUrl = "$directBase$fileId"
                $results += $directUrl

                [PSCustomObject]@{
                    Original  = $link
                    FileId    = $fileId
                    DirectUrl = $directUrl
                }
            }
            else {
                Write-Warning "Could not extract a file ID from: $link"
                [PSCustomObject]@{
                    Original  = $link
                    FileId    = $null
                    DirectUrl = $null
                }
            }
        }
    }

    end {
        if ($Copy -and $results.Count -gt 0) {
            $clipText = $results -join "`n"
            try {
                $clipText | Set-Clipboard
                Write-Host "`n+ $($results.Count) link(s) copied to clipboard." -ForegroundColor Green
            }
            catch {
                Write-Warning "Could not copy to clipboard: $_"
            }
        }
    }
}


function Save-GDriveFile {
<#
.SYNOPSIS
    Downloads a file from a Google Drive sharing link.

.PARAMETER Url
    The Google Drive sharing URL.

.PARAMETER Destination
    Folder or full file path to save the download. Defaults to current directory.

.PARAMETER FileName
    Override the output file name.

.EXAMPLE
    Save-GDriveFile -Url "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view" -Destination "C:\Downloads"
#>
    [CmdletBinding()]
    param (
        [Parameter(Mandatory, Position = 0)]
        [string]$Url,

        [Parameter(Position = 1)]
        [string]$Destination = (Get-Location).Path,

        [Parameter()]
        [string]$FileName
    )

    $converted = Convert-GDriveLink -Url $Url | Select-Object -First 1

    if (-not $converted.DirectUrl) {
        Write-Error "Failed to convert the URL. Aborting download."
        return
    }

    Write-Host "Direct URL : $($converted.DirectUrl)" -ForegroundColor Cyan

    if (Test-Path $Destination -PathType Container) {
        $outFile = if ($FileName) {
            Join-Path $Destination $FileName
        }
        else {
            Join-Path $Destination "gdrive_$($converted.FileId)"
        }
    }
    else {
        $outFile = $Destination
    }

    Write-Host "Saving to  : $outFile" -ForegroundColor Cyan

    try {
        $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
        $response = Invoke-WebRequest -Uri $converted.DirectUrl `
                                      -WebSession $session `
                                      -MaximumRedirection 5 `
                                      -UseBasicParsing

        if ($response.Content -match 'confirm=([0-9A-Za-z_]+)') {
            $confirmToken = $Matches[1]
            $confirmUrl   = "$($converted.DirectUrl)&confirm=$confirmToken"
            Write-Host "Large-file confirmation required - retrying with token..." -ForegroundColor Yellow
            Invoke-WebRequest -Uri $confirmUrl `
                              -WebSession $session `
                              -OutFile $outFile `
                              -UseBasicParsing
        }
        else {
            [System.IO.File]::WriteAllBytes($outFile, $response.Content)
        }

        Write-Host "+ Download complete: $outFile" -ForegroundColor Green
    }
    catch {
        Write-Error "Download failed: $_"
    }
}


# Entry point when run as a script (not dot-sourced)
if ($MyInvocation.InvocationName -ne '.') {

    Write-Host ""
    Write-Host "  Google Drive Link Converter" -ForegroundColor Cyan
    Write-Host "  -------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "  Functions loaded:" -ForegroundColor Gray
    Write-Host "    Convert-GDriveLink  -- convert one or more URLs" -ForegroundColor White
    Write-Host "    Save-GDriveFile     -- convert + download a file" -ForegroundColor White
    Write-Host ""
    Write-Host "  Quick examples:" -ForegroundColor Gray
    Write-Host '    Convert-GDriveLink "https://drive.google.com/file/d/FILE_ID/view"' -ForegroundColor Yellow
    Write-Host '    Convert-GDriveLink "https://drive.google.com/open?id=FILE_ID" -Copy' -ForegroundColor Yellow
    Write-Host '    Save-GDriveFile    "https://drive.google.com/file/d/FILE_ID/view" -Destination C:\Downloads' -ForegroundColor Yellow
    Write-Host ""

    $sample = "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74Y/view?usp=sharing"
    Write-Host "  Demo conversion:" -ForegroundColor Gray
    Convert-GDriveLink -Url $sample | Format-List
}