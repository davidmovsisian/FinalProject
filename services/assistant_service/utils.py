from models import PropertyListing
import json

def listing_to_text(listing: PropertyListing) -> str:
    features = ", ".join(listing.features) if listing.features else "no special features"
    conditions_payload = [condition.model_dump() for condition in listing.conditions]
    conditions_text = conditions_to_text(conditions_payload)
    conditions_part = f" Conditions: {conditions_text}." if conditions_text else ""
    return (
        f"Property type: {listing.property_type}. "
        f"Location: {listing.location}. "
        f"Price: {listing.price}. "
        f"Overall condition: {listing.overall_condition}. "
        f"Living rooms: {listing.living_room}. "
        f"Bedrooms: {listing.bed_rooms}. "
        f"Kitchens: {listing.kitchen}. "
        f"Bathrooms: {listing.bath_rooms}. "
        f"Storage: {listing.storage}. "
        f"Features: {features}."
        f"{conditions_part}"
    )

def conditions_to_text(conditions: list[dict]) -> str:
    return "; ".join(
        (
            f"{condition.get('type', 'unknown')}"
            f" score={condition.get('condition_score', 'unknown')}"
            f" confidence={condition.get('confidence', 'unknown')}"
        )
        for condition in conditions
    )