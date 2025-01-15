"""
When ran, this generates a token.json which is used as credentials when accessing Youtube Data API
"""
from google_auth_oauthlib.flow import InstalledAppFlow

# Define the scope for YouTube Data API
scopes = ['https://www.googleapis.com/auth/youtube.readonly']
client_secrets_file_path = '/Users/andyshi/Documents/AI_livestream_local_pipeline/google-services-files/pull_youtube_messages_credentials.json'

# Run the OAuth flow to get credentials
flow = InstalledAppFlow.from_client_secrets_file(
    client_secrets_file_path, scopes=scopes)

# Use run_local_server() to perform authentication
creds = flow.run_local_server(port=0)

# Save the credentials to a token file, transfered later into google colab
with open('google-services-files/token.json', 'w') as token:
    token.write(creds.to_json())
