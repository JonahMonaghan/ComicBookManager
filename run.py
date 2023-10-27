from app.app import app
app.run(ssl_context=("ComicBookManager\SSL\cert.pem", "ComicBookManager\SSL\key.pem"),debug=True)