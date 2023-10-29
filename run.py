from app.app import app
app.run(ssl_context=("SSL\cert.pem", "SSL\key.pem"),debug=True)