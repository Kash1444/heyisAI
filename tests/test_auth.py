# tests/test_auth.py

from app.services.gmail_auth_service import gmail_auth_service


def test_auth_url_generation():
    """Verify we can generate a valid Google OAuth URL."""
    url, state = gmail_auth_service.get_authorization_url()

    assert "accounts.google.com" in url
    assert "oauth2" in url
    assert len(state) > 0

    print(f"Auth URL generated successfully")
    print(f"State token  : {state[:10]}...")
    print(f"URL preview  : {url[:80]}...")


def test_auth_status_unauthenticated():
    """Before any login, status should be unauthenticated."""
    # Only run this if no token file exists
    from pathlib import Path
    if not Path("token.json").exists():
        status = gmail_auth_service.is_authenticated()
        assert status == False
        print("Correctly reports: not authenticated")
    else:
        print("token.json exists — skipping unauthenticated test")


if __name__ == "__main__":
    test_auth_url_generation()
    test_auth_status_unauthenticated()
    print("\nAuth service tests passed!")
