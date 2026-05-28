# tests/test_gmail_service.py

from app.services.gmail_service import gmail_service


def test_list_recent_emails():
    """Fetch 5 most recent inbox emails and display them."""
    print("\nFetching 5 most recent emails...")
    emails = gmail_service.list_emails(max_results=5)

    assert len(emails) > 0, "No emails returned — check credentials"

    for email in emails:
        print(f"\n{'─'*50}")
        print(f"ID      : {email.id}")
        print(f"From    : {email.sender}")
        print(f"Subject : {email.subject}")
        print(f"Date    : {email.date}")
        print(f"Snippet : {email.snippet[:80]}...")


def test_search_emails():
    """Search emails using a simple query."""
    print("\n\nSearching for emails...")

    # Change this to something you know exists in your Gmail
    emails = gmail_service.search_emails(
        query="in:inbox",
        max_results=3
    )

    print(f"Found {len(emails)} emails")
    for email in emails:
        print(f"  → {email.subject[:60]}")


def test_get_full_email():
    """Fetch a full email with decoded body."""
    print("\n\nFetching full email content...")

    # First get a list to find an ID to test with
    emails = gmail_service.list_emails(max_results=1)

    if not emails:
        print("No emails found to test full fetch")
        return

    email_id = emails[0].id
    full_email = gmail_service.get_email_full(email_id)

    if full_email:
        print(f"Subject    : {full_email.subject}")
        print(f"From       : {full_email.sender}")
        print(f"Body text  : {full_email.body_text[:200]}...")
    else:
        print("Could not fetch full email")


if __name__ == "__main__":
    test_list_recent_emails()
    test_search_emails()
    test_get_full_email()
    print("\n\nGmail service tests complete!")