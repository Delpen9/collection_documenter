Local Development

🚀 Run Django

# Apply any pending migrations (only required once)
python manage.py migrate

# Start the Django server on 0.0.0.0:8000
python manage.py runserver 0.0.0.0:8000

⚡️ Run Streamlit

# Launch the Streamlit app on port 8501
streamlit run collection_viewer/app.py --server.port 8501

⸻

🔑 OAuth Flow
	1.	Kick off login
Open your browser at:

http://localhost:8000/oauth/login/


	2.	Complete Google sign-in
	3.	Redirect back to Streamlit with your session

⸻

🔗 Google OAuth Client

[Configure your OAuth client in Google Cloud Console]
(Authorized redirect URI must be http://localhost:8000/oauth/auth/callback/)

https://console.cloud.google.com/auth/clients/771174142379-7plbgb4o00f2huotsaqjjd7g6fglb54g.apps.googleusercontent.com?inv=1&invt=Ab30qA