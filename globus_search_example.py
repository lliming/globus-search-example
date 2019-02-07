#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, url_for, session, redirect, request, render_template
import globus_sdk
from globus_sdk import (GlobusError,GlobusAPIError)
import json
import time


app = Flask(__name__)
app.config.from_pyfile('globus_search_example.conf')

@app.route('/')
def index():
    """
    This could be any page you like, rendered by Flask.
    For this simple example, it will either redirect you to login, or print
    a simple message.
    """
    if not session.get('is_authenticated'):
         # display all this information on the web page
         return render_template('not-logged-in.html', pagetitle=app.config['APP_DISPLAY_NAME'], loginurl=url_for('login'))
    logout_uri = url_for('logout', _external=True)

    # prepare the actions links
    idslink = "https://auth.globus.org/v2/web/identities?client_id={}&redirect_uri={}&redirect_name={}"
    conslink = "https://auth.globus.org/v2/web/consents?client_id={}&redirect_uri={}&redirect_name={}"

    # display all this information on the web page
    return render_template('logged-in.html', pagetitle=app.config['APP_DISPLAY_NAME'], 
         fullname=str(session.get('realname')),
         username=str(session.get('identity')),
         logouturl=logout_uri,
         idsurl=idslink.format(app.config['APP_CLIENT_ID'],url_for('index',_external=True),app.config['APP_DISPLAY_NAME']),
         consentsurl=conslink.format(app.config['APP_CLIENT_ID'],url_for('index',_external=True),app.config['APP_DISPLAY_NAME']))

@app.route('/login')
def login():
    """
    Login via Globus Auth.
    May be invoked in one of two scenarios:

      1. Login is starting, no state in Globus Auth yet
      2. Returning to application during login, already have short-lived
         code from Globus Auth to exchange for tokens, encoded in a query
         param
    """
    # the redirect URI, as a complete URI (not relative path)
    redirect_uri = url_for('login', _external=True)

    auth_client = load_app_client()
    auth_client.oauth2_start_flow(redirect_uri, 
            requested_scopes='openid email profile urn:globus:auth:scope:search.api.globus.org:all')

    # If there's no "code" query string parameter, we're in this route
    # starting a Globus Auth login flow.
    # Redirect out to Globus Auth
    if 'code' not in request.args:
        auth_uri = auth_client.oauth2_get_authorize_url()
        return redirect(auth_uri)
    # If we do have a "code" param, we're coming back from Globus Auth
    # and can start the process of exchanging an auth code for a token.
    else:
        code = request.args.get('code')
        tokens_response = auth_client.oauth2_exchange_code_for_tokens(code)
        ids = tokens_response.decode_id_token()
        session.update(
                tokens=tokens_response.by_resource_server,
                id_token=ids,
                username=ids['sub'],
                identity=ids['preferred_username'],
                realname=ids['name'],
                is_authenticated=True
                )
        return redirect(url_for('index'))

@app.route("/logout")
def logout():
    """
    - Revoke the tokens with Globus Auth.
    - Destroy the session state.
    - Redirect the user to the Globus Auth logout page.
    """
    client = load_app_client()

    # Revoke the tokens with Globus Auth
    for token in (token_info['access_token']
                  for token_info in session['tokens'].values()):
        client.oauth2_revoke_token(token)

    # Destroy the session state
    session.clear()

    # the return redirection location to give to Globus AUth
    redirect_uri = url_for('index', _external=True)

    # build the logout URI with query params
    # there is no tool to help build this (yet!)
    globus_logout_url = (
        'https://auth.globus.org/v2/web/logout' +
        '?client_id={}'.format(app.config['APP_CLIENT_ID']) +
        '&redirect_uri={}'.format(redirect_uri) +
        '&redirect_name={}'.format(app.config['APP_DISPLAY_NAME']))

    # Redirect the user to the Globus Auth logout page
    return redirect(globus_logout_url)


@app.route("/privacy")
def privacy():
    return render_template('privacy.html', pagetitle=app.config['APP_DISPLAY_NAME'],
                           returnurl=url_for('index'))

def load_app_client():
    return globus_sdk.ConfidentialAppAuthClient(
        app.config['APP_CLIENT_ID'], app.config['APP_CLIENT_SECRET'])


# actually run the app if this is called as a script
if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5000,debug=True,ssl_context=('./keys/server.crt', './keys/server.key'))

