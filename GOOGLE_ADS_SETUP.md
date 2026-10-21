# Google Ads setup

## Streamlit configuration

Google Ads OAuth settings are read from Streamlit Secrets:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`

Create a **Web application** OAuth client in the Google Cloud project that will own
the Google Ads API access. Register the exact HTTPS redirect URI used by the
deployed Streamlit app in **Authorized redirect URIs** and set the same value in
`GOOGLE_OAUTH_REDIRECT_URI`. Enable the Google Ads API in that same Cloud project
and complete Google's OAuth consent-screen requirements, including verification
or test-user configuration where applicable.

## Google Ads API access

Google retired developer tokens on **September 9, 2026**. The current onboarding
and access-level management are tied to the Google Cloud project that owns the
OAuth client ID and secret. Do not create a new developer-token setup as part of
this integration; the current code intentionally does not send a developer-token
header.

After enabling the API, open the **Google Ads API Overview** page in Google Cloud
Console and check the project's access level. Test access permits test accounts
only. To query live advertiser accounts, the project must have production access
(for example, Explorer access, subject to Google's limits and eligibility). If
the API responds with an access-level error, check that access level in the same
Cloud project that owns the OAuth client used by Streamlit.

Official guidance:
- [Developer token sunset and migration](https://developers.google.com/google-ads/api/docs/api-policy/developer-token)
- [Google Ads API access levels](https://developers.google.com/google-ads/api/docs/api-policy/access-levels)
- [Set up a Google API Console project](https://developers.google.com/google-ads/api/docs/oauth/cloud-project)

## Client workflow

Each client must connect their own Google account and grant the Google Ads scope.
That user must have access to the Google Ads customer account entered in Agencia
OS. When access is through a manager account, enter its customer ID in the
optional manager field.

Access and refresh tokens are held only in the current Streamlit session. They
are not persisted to files, URLs, or application logs; clients may need to
reconnect in a new session. OAuth and Google Ads API requests use HTTPS.

## Reports and metric interpretation

Reports are read-only, segmented by date, and use the selected date range.
Google's conversion value appears in the common `Revenue` column, but reflects
the values configured for that account's conversion actions and may not equal
monetary sales. Empty results mean the API returned no campaign rows for the
selected account and period; they are not converted into zero-valued campaigns.
