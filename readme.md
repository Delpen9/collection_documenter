Start NGINX:
brew services start nginx

Stop/Restart NGINX:
brew services stop nginx
brew services restart nginx

Running Django locally:
python manage.py migrate # ONLY if this hasn't been done yet
python manage.py runserver 0.0.0.0:8000

Running Streamlit locally:
streamlit run collection_viewer/app.py --server.port 8501


The navigate here in the browser:
http://localhost:8000/oauth/login/

Then login.

Link to Google Login API Configuration:
https://console.cloud.google.com/auth/clients/771174142379-7plbgb4o00f2huotsaqjjd7g6fglb54g.apps.googleusercontent.com?inv=1&invt=Ab30qA