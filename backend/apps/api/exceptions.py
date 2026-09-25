from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException


def custom_exception_handler(exc, context):
    """
    Standardizes all API error responses to the uniform JSON shape:
    {
        "code": "<string_code>",
        "detail": "<human_readable_message>",
        "fields": { ... }
    }
    Guarantees no stack traces, raw internal errors, or unhandled shapes leak to the client.
    """
    response = exception_handler(exc, context)

    if response is not None:
        code = "error"
        detail = "An error occurred."
        fields = {}

        if isinstance(response.data, dict):
            if "detail" in response.data:
                detail = str(response.data["detail"])
                # Extract code from detail if DRF ErrorDetail
                if hasattr(response.data["detail"], "code"):
                    code = response.data["detail"].code
            else:
                detail = "One or more fields failed validation."
                fields = response.data
                code = "validation_error"
        elif isinstance(response.data, list):
            detail = str(response.data[0]) if response.data else "Validation error."
            fields = {"non_field_errors": response.data}
            code = "validation_error"
        else:
            detail = str(response.data)

        # Standardize code names based on HTTP status
        status_code = response.status_code
        if status_code == 400 and code == "error":
            code = "validation_error"
        elif status_code == 401:
            code = getattr(exc, "default_code", "unauthenticated")
        elif status_code == 403:
            code = "permission_denied"
        elif status_code == 404:
            code = "not_found"
        elif status_code == 429:
            code = "throttled"

        response.data = {
            "code": code,
            "detail": detail,
            "fields": fields,
        }

    return response
