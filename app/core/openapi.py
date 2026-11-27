def configure_service_security(application):
    original = application.openapi

    def secured_openapi():
        schema = original()
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["ServiceApiKey"] = {
            "type": "apiKey", "in": "header", "name": "X-API-Key",
        }
        for path, methods in schema["paths"].items():
            if path.startswith("/api/"):
                for operation in methods.values():
                    if isinstance(operation, dict) and "responses" in operation:
                        operation["security"] = [{"ServiceApiKey": []}]
        return schema

    application.openapi = secured_openapi
