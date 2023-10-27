import msal
from flask import request, redirect, url_for, session, render_template
import app_config

class AuthManager:

    def __init__(self, app):
        self.app = app

    def register_auth_routes(self):
        self.app.add_url_rule("/login", "login", self.login)
        self.app.add_url_rule("/get_token", "authorized", self.authorized)
        self.app.add_url_rule("/logout", "logout", self.logout)

    def login(self):
        session["flow"] = self._build_auth_code_flow(scopes=app_config.SCOPE)
        return render_template("login.html", auth_uri=session["flow"]["auth_uri"])
      
    def authorized(self):
        try:
            cache = self._load_cache()
            result = self._build_msal_app(cache=cache).acquire_token_by_auth_code_flow(
                session.get("flow", {}), request.args)
            if "error" in result:
                print(f"Authorization error: {result['error']}")
                return render_template("auth_error.html", result=result)
            session["user"] = result.get("id_token_claims")
            session["access_token"] = result["access_token"]            
            self._save_cache(cache)
        except Exception as e:
            print(f"Exception during authentication: {str(e)}")
            pass 
        return redirect(url_for("index"))
    
    def logout(self):
        session.clear()  # Wipe out user and its token cache from session
        return redirect(  # Also logout from your tenant's web session
            app_config.AUTHORITY + "/oauth2/v2.0/logout" +
            "?post_logout_redirect_uri=" + url_for("index", _external=True))
    
    def _build_msal_app(self, cache=None, authority=None):
        return msal.ConfidentialClientApplication(
        app_config.CLIENT_ID, authority=authority or app_config.AUTHORITY,
        client_credential=app_config.CLIENT_SECRET, token_cache=cache)

    def _build_auth_code_flow(self, authority=None, scopes=None):
        return self._build_msal_app(authority=authority).initiate_auth_code_flow(
            scopes or [],
            redirect_uri=url_for("authorized", _external=True))
    
    def _load_cache(self):
        cache = msal.SerializableTokenCache()
        if session.get("token_cache"):
            cache.deserialize(session["token_cache"])
        return cache

    def _save_cache(self, cache):
        if cache.has_state_changed:
            session["token_cache"] = cache.serialize()

    def _get_token_from_cache(self, scope=None):
        cache = self._load_cache()  # This web app maintains one cache per session
        cca = self._build_msal_app(cache=cache)
        accounts = cca.get_accounts()
        if accounts:  # So all account(s) belong to the current signed-in user
            result = cca.acquire_token_silent(scope, account=accounts[0])
            self._save_cache(cache)
            return result