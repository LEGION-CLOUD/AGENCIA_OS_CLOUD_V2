# Google Ads setup

Google Ads OAuth settings are read from Streamlit Secrets:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`

Create a Google OAuth web client and register the exact HTTPS redirect URI used
by the deployed Streamlit app. Configure the same URI in Streamlit Secrets.
Enable Google Ads API for the associated Google Cloud project and complete
Google's OAuth consent-screen requirements, including verification or test-user
configuration where applicable.

Each client must connect their own Google account and grant the Google Ads
scope. They must also have access to the customer account entered in the app.
When access is through a manager account, enter its customer ID in the optional
manager field.

Access and refresh tokens are held only in the current Streamlit session. They
are not persisted to files, URLs, or logs; users may need to reconnect in a new
session. The integration uses HTTPS for OAuth and Google Ads API requests. It
does not send a developer-token header; confirm the Google Cloud project's
current API eligibility and migration status before a live account test.

Reports are read-only, segmented by date, and use the selected date range.
Google's conversion value is shown in the common `Revenue` column, but reflects
the values configured for that account's conversion actions and may not equal
monetary sales. An empty report means the API returned no campaign rows for the
selected account and period; it is not converted into zero-valued campaigns.
