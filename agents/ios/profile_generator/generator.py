"""Apple Configuration Profile (.mobileconfig) generator.

Generates a signed or unsigned XML plist that a parent can download and
install on a child's iOS/iPadOS device. No MDM server required for basic
restrictions — just AirDrop or email the file to the device.

Apple documentation:
  https://developer.apple.com/documentation/devicemanagement/restrictions
"""
import uuid
import plistlib
from datetime import datetime
from typing import Optional


def generate_profile(
    child_name: str,
    organization: str = "GuardHome",
    disable_vpn_install: bool = True,
    disable_doh: bool = True,
    disable_hotspot: bool = False,
    disable_airdrop: bool = False,
    content_rating_region: str = "us",
    max_movie_rating: int = 500,      # 500 = PG-13 (US), 1000 = All
    max_tv_rating: int = 500,
    allow_app_install: bool = True,
    restrict_safari: bool = False,
    force_encrypted_backup: bool = True,
    dns_servers: Optional[list] = None,
) -> bytes:
    """Return the .mobileconfig file as bytes."""

    profile_uuid     = str(uuid.uuid4()).upper()
    restriction_uuid = str(uuid.uuid4()).upper()
    dns_uuid         = str(uuid.uuid4()).upper()

    payloads = [_restrictions_payload(
        uuid=restriction_uuid,
        disable_vpn_install=disable_vpn_install,
        disable_hotspot=disable_hotspot,
        disable_airdrop=disable_airdrop,
        max_movie_rating=max_movie_rating,
        max_tv_rating=max_tv_rating,
        allow_app_install=allow_app_install,
        restrict_safari=restrict_safari,
        force_encrypted_backup=force_encrypted_backup,
        content_rating_region=content_rating_region,
    )]

    if dns_servers:
        payloads.append(_dns_payload(uuid=dns_uuid, servers=dns_servers))

    if disable_doh:
        payloads.append(_doh_block_payload())

    profile = {
        "PayloadContent":      payloads,
        "PayloadDescription":  f"GuardHome parental controls for {child_name}",
        "PayloadDisplayName":  f"GuardHome — {child_name}",
        "PayloadIdentifier":   f"com.guardhome.profile.{profile_uuid.lower()}",
        "PayloadOrganization": organization,
        "PayloadRemovalDisallowed": False,  # True requires supervision
        "PayloadType":         "Configuration",
        "PayloadUUID":         profile_uuid,
        "PayloadVersion":      1,
    }

    return plistlib.dumps(profile, fmt=plistlib.FMT_XML)


def _restrictions_payload(uuid: str, **kwargs) -> dict:
    payload = {
        "PayloadType":        "com.apple.applicationaccess",
        "PayloadVersion":     1,
        "PayloadIdentifier":  f"com.guardhome.restrictions.{uuid.lower()}",
        "PayloadUUID":        uuid,
        "PayloadDisplayName": "Restrictions",

        # Content ratings
        "ratingRegion":         kwargs.get("content_rating_region", "us"),
        "ratingMovies":         kwargs.get("max_movie_rating", 500),
        "ratingTVShows":        kwargs.get("max_tv_rating", 500),
        "ratingApps":           1000,  # Allow all age-appropriate apps

        # App Store / install
        "allowAppInstallation": kwargs.get("allow_app_install", True),
        "allowInAppPurchases":  False,
        "requireStorePasswordForPurchases": True,

        # VPN
        "allowVPNCreation": not kwargs.get("disable_vpn_install", True),

        # Safari
        "safariAllowAutoFill":  False,
        "safariForcePopupBlocker": True,
        "safariForceFraudWarning": True,

        # Hotspot
        "allowPersonalHotspot": not kwargs.get("disable_hotspot", False),

        # AirDrop
        "allowAirDrop": not kwargs.get("disable_airdrop", False),

        # iCloud
        "allowCloudBackup":    True,
        "allowCloudDocumentSync": False,
        "allowManagedAppsCloudSync": False,

        # Privacy
        "allowDiagnosticSubmission": False,
        "allowActivityContinuation": False,

        # Backup
        "forceEncryptedBackup": kwargs.get("force_encrypted_backup", True),

        # Siri
        "allowAssistantWhileLocked": False,
    }
    return payload


def _dns_payload(uuid: str, servers: list) -> dict:
    """Override DNS servers on-device (strongest enforcement with supervision)."""
    return {
        "PayloadType":        "com.apple.dnsSettings.managed",
        "PayloadVersion":     1,
        "PayloadIdentifier":  f"com.guardhome.dns.{uuid.lower()}",
        "PayloadUUID":        uuid,
        "PayloadDisplayName": "DNS Settings",
        "DNSProtocol":        "Clear",   # Plain DNS (not DoH)
        "ServerAddresses":    servers,
    }


def _doh_block_payload() -> dict:
    """Web content filter payload that blocks known DoH providers."""
    return {
        "PayloadType":        "com.apple.webcontent-filter",
        "PayloadVersion":     1,
        "PayloadIdentifier":  f"com.guardhome.doh-block.{str(uuid.uuid4()).upper().lower()}",
        "PayloadUUID":        str(uuid.uuid4()).upper(),
        "PayloadDisplayName": "Block DoH Bypass",
        "FilterType":         "BuiltIn",
        "AutoFilterEnabled":  False,
        "DenyListURLs": [
            "https://cloudflare-dns.com/dns-query",
            "https://dns.google/dns-query",
            "https://dns9.quad9.net/dns-query",
            "https://doh.opendns.com/dns-query",
        ],
    }


def profile_filename(child_name: str) -> str:
    safe = "".join(c for c in child_name if c.isalnum() or c in " _-").strip()
    return f"guardhome_{safe.lower().replace(' ', '_')}.mobileconfig"
