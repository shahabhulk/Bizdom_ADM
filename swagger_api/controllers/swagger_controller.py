import json
from odoo import http
from odoo.http import request


class SwaggerController(http.Controller):

    # Renders the Swagger UI Page
    @http.route('/bizdom-api', type='http', auth='public', sitemap=False)
    def swagger_ui(self, **kw):
        return request.render('swagger_api.swagger_ui_template')

    # Returns the OpenAPI JSON for Swagger UI
    @http.route('/api-docs.json', type='http', auth='public', methods=['GET'], csrf=False)
    def swagger_json(self, **kwargs):
        swagger_doc = {
            "openapi": "3.0.0",
            "info": {
                "title": "Bizdom Dashboard API",
                "version": "1.0.0",
                "description": "API documentation for Bizdom Dashboard"
            },
            "servers": [
                {"url": "/", "description": "Odoo Server"}
            ],
            "paths": {
                "/api/login": {
                    "post": {
                        "tags": ["Authentication"],
                        "summary": "Login and get JWT token",
                        "description": "Authenticates user using username and password, returns JWT token.",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "username": {"type": "string", "example": "admin"},
                                            "password": {"type": "string", "example": "1"}
                                        },
                                        "required": ["username", "password"]
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Login successful",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {"type": "integer", "example": 200},
                                                "message": {"type": "string", "example": "Login successful"},
                                                "uid": {"type": "integer", "example": 2},
                                                "token": {"type": "string", "example": "eyJhbGciOi..."}
                                            }
                                        }
                                    }
                                }
                            },
                            "400": {"description": "Missing username or password"},
                            "401": {"description": "Invalid credentials"},
                            "500": {"description": "Internal Server Error"}
                        }
                    }
                },
                "/api/dashboard": {
                    "get": {
                        "tags": ["Dashboard"],
                        "summary": "Get dashboard data",
                        "description": "Retrieves dashboard KPIs and metrics.",
                        "parameters": [
                            {
                                "name": "startDate",
                                "in": "query",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "Start date (DD-MM-YYYY)",
                                    "example": "01-01-2025"
                                }
                            },
                            {
                                "name": "endDate",
                                "in": "query",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "End date (DD-MM-YYYY)",
                                    "example": "31-12-2025"
                                }
                            },
                            {
                                "name": "filterType",
                                "in": "query",
                                "required": True,
                                "schema": {
                                    "type": "string",
                                    "enum": ["Custom", "WTD", "MTD", "YTD"],
                                    "description": "Type of filter to apply"
                                }
                            }
                        ],
                        "responses": {
                            "200": {"description": "Success"},
                            "400": {"description": "Invalid input"},
                            "401": {"description": "Unauthorized"},
                            "500": {"description": "Internal error"}
                        },
                        "security": [{"bearerAuth": []}]
                    }
                },
                "/api/score/toggle_favorite": {
                    "post": {
                        "tags": ["Favorite Scores"],
                        "summary": "Toggle favorite score",
                        "description": "Toggle favorite score",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "pillar_id": {"type": "integer", "example": 1},
                                            "score_id": {"type": "integer", "example": 1},
                                            "favorite": {"type": "boolean", "example": True}
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {"description": "Success"},
                            "400": {"description": "Invalid input"},
                            "401": {"description": "Unauthorized"},
                            "500": {"description": "Internal error"}
                        },
                        "security": [{"bearerAuth": []}]
                    }

                },
                "/api/score/overview": {
                    "get": {
                        "tags": ["Score Q1 Overview"],
                        "summary": "Get score overall overview data",
                        "description": "Retrieves overview data for a specific score, with optional date filtering.",
                        "parameters": [
                            {
                                "name": "scoreId",
                                "in": "query",
                                "required": True,
                                "schema": {
                                    "type": "integer",
                                    "description": "ID of the score to get overview for",
                                    "example": 1
                                }
                            },
                            {
                                "name": "startDate",
                                "in": "query",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "Start date in DD-MM-YYYY format (required for Custom filter type)",
                                    "example": "01-01-2025"
                                }
                            },
                            {
                                "name": "endDate",
                                "in": "query",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "End date in DD-MM-YYYY format (required for Custom filter type)",
                                    "example": "31-12-2025"
                                }
                            },
                            {
                                "name": "filterType",
                                "in": "query",
                                "required": True,
                                "schema": {
                                    "type": "string",
                                    "enum": ["Custom", "WTD", "MTD", "YTD"],
                                    "description": "Type of filter to apply",
                                    "example": "Custom"
                                }
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {
                                                    "type": "integer",
                                                    "example": 200
                                                },
                                                "overview": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "start_date": {
                                                                "type": "string",
                                                                "example": "01-01-2025"
                                                            },
                                                            "end_date": {
                                                                "type": "string",
                                                                "example": "31-12-2025"
                                                            },
                                                            "actual_value": {
                                                                "type": "number",
                                                                "format": "float",
                                                                "example": 1500.75
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "400": {
                                "description": "Invalid input or missing required fields"
                            },
                            "401": {
                                "description": "Unauthorized - Invalid or missing token"
                            },
                            "404": {
                                "description": "User not found"
                            },
                            "500": {
                                "description": "Internal server error"
                            }
                        },
                        "security": [{"bearerAuth": []}]
                    }
                },
                "/api/score/overview/department": {
                    "get": {
                        "tags": ["Score Q2 Overview"],
                        "summary": "Get score department wise overview data",
                        "description": "Retrieves department overview data for a specific score, with optional date filtering.(scoreId:1-2-3-4,labour-Customer Satisfaction-TAT-Leads)",
                        "parameters": [
                            {
                                "name": "scoreId",
                                "in": "query",
                                "required": True,
                                "schema": {
                                    "type": "integer",
                                    "description": "ID of the score to get overview for",
                                    "example": 1
                                }
                            },
                            {
                                "name": "startDate",
                                "in": "query",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "Start date in DD-MM-YYYY format (required for Custom filter type)",
                                    "example": "01-01-2025"
                                }
                            },
                            {
                                "name": "endDate",
                                "in": "query",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "End date in DD-MM-YYYY format (required for Custom filter type)",
                                    "example": "31-12-2025"
                                }
                            },
                            {
                                "name": "filterType",
                                "in": "query",
                                "required":False,
                                "schema": {
                                    "type": "string",
                                    "enum": ["Custom", "WTD", "MTD", "YTD"],
                                    "description": "Type of filter to apply",
                                    "example": "Custom"
                                }
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {
                                                    "type": "integer",
                                                    "example": 200
                                                },
                                                "message": {
                                                    "type": "string",
                                                    "example": "Score Department Overview"
                                                },
                                                "score_id": {
                                                    "type": "integer",
                                                    "example": 4
                                                },
                                                "score_name": {
                                                    "type": "string",
                                                    "example": "Leads"
                                                },
                                                "overview_department": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "start_date": {
                                                                "type": "string",
                                                                "example": "01-10-2025"
                                                            },
                                                            "end_date": {
                                                                "type": "string",
                                                                "example": "10-10-2025"
                                                            },
                                                            "max_value": {
                                                                "type": "string",
                                                                "example": ""
                                                            },
                                                            "min_value": {
                                                                "type": "string",
                                                                "example": ""
                                                            },
                                                            "total_actual_value": {
                                                                "type": "integer",
                                                                "example": 4
                                                            },
                                                            "department": {
                                                                "type": "array",
                                                                "items": {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "department_id": {
                                                                            "type": "integer",
                                                                            "example": 13
                                                                        },
                                                                        "department_name": {
                                                                            "type": "string",
                                                                            "example": "Online"
                                                                        },
                                                                        "max_value": {
                                                                            "type": "string",
                                                                            "example": ""
                                                                        },
                                                                        "min_value": {
                                                                            "type": "string",
                                                                            "example": ""
                                                                        },
                                                                        "conversion_value": {
                                                                            "type": "integer",
                                                                            "example": 1
                                                                        },
                                                                        "actual_value": {
                                                                            "type": "integer",
                                                                            "example": 2
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "400": {
                                "description": "Bad Request - Missing or invalid scoreId",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {
                                                    "type": "integer",
                                                    "example": 400
                                                },
                                                "message": {
                                                    "type": "string",
                                                    "example": "scoreId is required"
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "401": {
                                "description": "Unauthorized - Invalid, expired, or missing token",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {
                                                    "type": "integer",
                                                    "example": 401
                                                },
                                                "message": {
                                                    "type": "string",
                                                    "enum": ["Token missing", "Token expired", "Invalid token"],
                                                    "example": "Token missing"
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "404": {
                                "description": "Not Found - User or Score record not found",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {
                                                    "type": "integer",
                                                    "example": 404
                                                },
                                                "message": {
                                                    "type": "string",
                                                    "enum": ["User not found or multiple users", "Score record not found"],
                                                    "example": "Score record not found"
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "500": {
                                "description": "Internal server error"
                            }
                        },
                        "security": [{"bearerAuth": []}]
                    }
                },
                "/api/score/overview/employee": {
                    "get": {
                        "tags": ["Score Q3 Overview"],
                        "summary": "Get score employee-wise overview data",
                        "description": "Retrieves employee overview data for a specific score, with optional date filtering. Parameters: scoreId (required) - ID of the score to get overview for, startDate (optional) - Start date for filtering, endDate (optional) - End date for filtering, filterType (optional) - Type of filter to apply (Custom, WTD, MTD, YTD).(scoreId:1-2-3-4,labour-Customer Satisfaction-TAT-Leads)(departmentId:8-9,Bodyshop-Workshop)(departmentId:13-14,Online-Offline)",
                        "parameters": [
                            {
                                "name": "scoreId",
                                "in": "query",
                                "required": True,
                                "schema": {
                                    "type": "integer",
                                    "description": "ID of the score to get overview for",
                                    "example": 1
                                }
                            },
                            {
                                "name": "departmentId",
                                "in": "query",
                                "required": True,
                                "schema": {
                                    "type": "integer",
                                    "description": "ID of the department to get overview for",
                                    "example": 13
                                }
                            },
                            {
                                "name": "startDate",
                                "in": "query",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "Start date in DD-MM-YYYY format (required for Custom filter type)",
                                    "example": "01-10-2025"
                                }
                            },
                            {
                                "name": "endDate",
                                "in": "query",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "End date in DD-MM-YYYY format (required for Custom filter type)",
                                    "example": "31-10-2025"
                                }
                            },
                            {
                                "name": "filterType",
                                "in": "query",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "enum": ["Custom", "WTD", "MTD", "YTD"],
                                    "description": "Type of filter to apply",
                                    "example": "MTD"
                                }
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {
                                                    "type": "integer",
                                                    "example": 200
                                                },
                                                "message": {
                                                    "type": "string",
                                                    "example": "Employee Overview"
                                                },
                                                "score_id": {
                                                    "type": "integer",
                                                    "example": 4
                                                },
                                                "score_name": {
                                                    "type": "string",
                                                    "example": "Leads"
                                                },
                                                "department_id": {
                                                    "type": "integer",
                                                    "example": 13
                                                },
                                                "department_name": {
                                                    "type": "string",
                                                    "example": "Online"
                                                },
                                                "overview_source": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "start_date": {
                                                                "type": "string",
                                                                "example": "01-10-2025"
                                                            },
                                                            "end_date": {
                                                                "type": "string",
                                                                "example": "10-10-2025"
                                                            },
                                                            "max_value": {
                                                                "type": "string",
                                                                "example": ""
                                                            },
                                                            "min_value": {
                                                                "type": "string",
                                                                "example": ""
                                                            },
                                                            "total_converted_value": {
                                                                "type": "integer",
                                                                "example": 1
                                                            },
                                                            "total_lead_value": {
                                                                "type": "integer",
                                                                "example": 2
                                                            },
                                                            "sources": {
                                                                "type": "array",
                                                                "items": {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "source_id": {
                                                                            "type": "integer",
                                                                            "example": 6
                                                                        },
                                                                        "source_name": {
                                                                            "type": "string",
                                                                            "example": "LinkedIn"
                                                                        },
                                                                        "max_value": {
                                                                            "type": "string",
                                                                            "example": ""
                                                                        },
                                                                        "min_value": {
                                                                            "type": "string",
                                                                            "example": ""
                                                                        },
                                                                        "conversion_value": {
                                                                            "type": "integer",
                                                                            "example": 1
                                                                        },
                                                                        "lead_value": {
                                                                            "type": "integer",
                                                                            "example": 1
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "400": {
                                "description": "Bad Request - Invalid input parameters"
                            },
                            "401": {
                                "description": "Unauthorized - Invalid or missing token"
                            },
                            "404": {
                                "description": "Employee not found"
                            },
                            "500": {
                                "description": "Internal Server Error"
                            }
                        },
                        "security": [{"bearerAuth": []}]
                    }
                }
            },
            "components": {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT"
                    }
                }
            }
        }

        return request.make_response(
            json.dumps(swagger_doc),
            headers=[('Content-Type', 'application/json')]
        )
