import os
os.environ['SUPABASE_URL'] = 'http://ietunkxgukxpeacoiigl.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlldHVua3hndWt4cGVhY29paWdsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDk1Njg3OSwiZXhwIjoxNzYwOTU2ODc5fQ.q1bc3mkGGkuxSNydkeBaNxZS-mVQj1nNmmgocHJkWf4'
os.environ['SUPABASE_ANON_KEY'] = 'sb_publishable_2J74WhPQQZ-U5qgbkUIAsQ_j_VHF4_7'

from src.email_sender import send_daily_email

print("Sending test email...")

send_daily_email(
    "Test - Daily AI Trend Report",
    "<h1>Test Successful!</h1><p>This is a test email.</p>"
)

print("Email sent!")
