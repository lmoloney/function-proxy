import azure.functions as func
import logging
import json
import requests
import re
from urllib.parse import urlencode, urlparse

# Define allowed patterns (wildcards supported)
ALLOWED_PATTERNS = [
    "api.example.com",
    "services.odata.org",
    "jsonplaceholder.*",
    "*.trusted.com",
    "10.0.1.4",  # Add your local IP
    "localhost",
    "127.0.0.1",
    "*",  # Matches any domain
    # Add your specific domains here for production
]

# Compile wildcard patterns to regex
def compile_patterns(patterns):
    regex_patterns = []
    for pattern in patterns:
        regex_pattern = re.escape(pattern).replace(r"\*", ".*")
        regex_pattern = f"^{regex_pattern}$"
        regex_patterns.append(re.compile(regex_pattern, re.IGNORECASE))
    return regex_patterns

REGEX_PATTERNS = compile_patterns(ALLOWED_PATTERNS)

def is_allowed(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    domain = parsed.netloc or parsed.path.split("/")[0]
    # Handle cases where netloc might include port
    if ':' in domain:
        domain = domain.split(':')[0]
    for regex in REGEX_PATTERNS:
        if regex.match(domain):
            return True
    return False

app = func.FunctionApp()

@app.route(route="proxy/{*endpoint}", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy_function(req: func.HttpRequest) -> func.HttpResponse:
    try:
        endpoint = req.route_params.get('endpoint')
        if not endpoint:
            error_msg = "No endpoint specified"
            logging.error(error_msg)
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=400,
                mimetype="application/json"
            )

        # Check for scheme override parameter (using an unlikely parameter name)
        scheme_override = req.params.get('__proxy_scheme')
        
        # Determine scheme
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            target_url = endpoint
        elif scheme_override:
            if scheme_override.lower() in ['http', 'https']:
                target_url = f"{scheme_override.lower()}://{endpoint}"
            else:
                error_msg = f"Invalid scheme: {scheme_override}. Only 'http' and 'https' are allowed."
                logging.error(error_msg)
                return func.HttpResponse(
                    json.dumps({"error": error_msg}),
                    status_code=400,
                    mimetype="application/json"
                )
        else:
            target_url = f"https://{endpoint}"

        # Allowlist check
        if not is_allowed(target_url):
            error_msg = f"Endpoint not allowed: {target_url}"
            logging.error(error_msg)
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=403,
                mimetype="application/json"
            )

        # Query parameters (exclude our special parameter)
        query_params = {k: v for k, v in req.params.items() if k != '__proxy_scheme'}
        if query_params:
            delimiter = "&" if "?" in target_url else "?"
            target_url += delimiter + urlencode(query_params)

        method = req.method.upper()

        # Prepare headers (exclude hop-by-hop headers)
        headers = {}
        for key, value in req.headers.items():
            if key.lower() not in ['host', 'connection', 'content-length', 'transfer-encoding']:
                headers[key] = value

        # Request body for applicable methods
        body = None
        if method in ['POST', 'PUT', 'PATCH']:
            try:
                body = req.get_body()
            except Exception as e:
                logging.warning(f"Could not read request body: {e}")

        logging.info(f"Proxying {method} request to: {target_url}")

        response = requests.request(
            method=method,
            url=target_url,
            headers=headers,
            data=body,
            timeout=30,
            verify=target_url.startswith("https://")
        )

        # Filter response headers
        response_headers = {}
        for key, value in response.headers.items():
            if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding', 'connection']:
                response_headers[key] = value

        return func.HttpResponse(
            body=response.content,
            status_code=response.status_code,
            headers=response_headers,
            mimetype=response.headers.get('content-type', 'application/json')
        )

    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        logging.error(error_msg)
        return func.HttpResponse(
            json.dumps({"error": error_msg}),
            status_code=502,
            mimetype="application/json"
        )
    except Exception as e:
        error_msg = f"Internal server error: {str(e)}"
        logging.error(error_msg)
        return func.HttpResponse(
            json.dumps({"error": error_msg}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="odata/{*endpoint}", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET", "POST"])
def odata_proxy_function(req: func.HttpRequest) -> func.HttpResponse:
    try:
        endpoint = req.route_params.get('endpoint')
        if not endpoint:
            error_msg = "No OData endpoint specified"
            logging.error(error_msg)
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=400,
                mimetype="application/json"
            )

        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            target_url = endpoint
        else:
            target_url = f"https://{endpoint}"

        if not is_allowed(target_url):
            error_msg = f"OData endpoint not allowed: {target_url}"
            logging.error(error_msg)
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=403,
                mimetype="application/json"
            )

        query_params = dict(req.params)
        if query_params:
            delimiter = "&" if "?" in target_url else "?"
            target_url += delimiter + urlencode(query_params)

        method = req.method.upper()

        # OData-specific headers
        headers = {
            'Accept': 'application/json;odata.metadata=minimal',
            'Content-Type': 'application/json',
            'OData-Version': '4.0'
        }
        for key, value in req.headers.items():
            if key.lower() not in ['host', 'connection', 'content-length', 'transfer-encoding', 'accept', 'content-type']:
                headers[key] = value

        body = None
        if method == 'POST':
            try:
                body = req.get_body()
            except Exception as e:
                logging.warning(f"Could not read request body: {e}")

        logging.info(f"Proxying OData {method} request to: {target_url}")

        response = requests.request(
            method=method,
            url=target_url,
            headers=headers,
            data=body,
            timeout=30,
            verify=target_url.startswith("https://")
        )

        response_headers = {}
        for key, value in response.headers.items():
            if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding', 'connection']:
                response_headers[key] = value

        return func.HttpResponse(
            body=response.content,
            status_code=response.status_code,
            headers=response_headers,
            mimetype=response.headers.get('content-type', 'application/json')
        )

    except requests.exceptions.RequestException as e:
        error_msg = f"OData request failed: {str(e)}"
        logging.error(error_msg)
        return func.HttpResponse(
            json.dumps({"error": error_msg}),
            status_code=502,
            mimetype="application/json"
        )
    except Exception as e:
        error_msg = f"Unexpected error in OData proxy: {str(e)}"
        logging.error(error_msg)
        return func.HttpResponse(
            json.dumps({"error": error_msg}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "healthy"}),
        status_code=200,
        mimetype="application/json"
    )
