from models import PropertyListing


def listing_to_text(listing: PropertyListing) -> str:
    features = ", ".join(listing.features) if listing.features else "no special features"
    return (
        f"Property type: {listing.property_type}. "
        f"Location: {listing.location}. "
        f"Price: {listing.price}. "
        f"Rooms: {listing.rooms_number}. "
        f"Features: {features}."
    )
