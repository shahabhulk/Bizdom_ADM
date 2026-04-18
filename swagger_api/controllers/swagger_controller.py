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
                },
                "/api/todos": {
                    "get": {
                        "tags": ["Todos"],
                        "summary": "List todos for the authenticated user",
                        "description": (
                            "Returns a paginated list of `project.task` records where the JWT user is an assignee. "
                            "Each todo includes a hydrated `user_ids` array (full user objects, not just ids)."
                        ),
                        "parameters": [
                            {
                                "name": "limit",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "default": 50, "maximum": 200, "example": 50}
                            },
                            {
                                "name": "offset",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "default": 0, "example": 0}
                            },
                            {
                                "name": "search",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "string", "description": "Case-insensitive match on todo name"}
                            },
                            {
                                "name": "pillar_id",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "description": "Filter by Bizdom pillar"}
                            },
                            {
                                "name": "assignee_id",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "description": "Filter by an additional assignee user id"}
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "List of todos",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {"type": "integer", "example": 200},
                                                "data": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "id": {"type": "integer", "example": 42},
                                                            "name": {"type": "string", "example": "Review Q1 dashboard"},
                                                            "description": {"type": "string", "example": "Check figures before Monday"},
                                                            "pillar_id": {"type": "integer", "nullable": True, "example": 1},
                                                            "pillar_name": {"type": "string", "nullable": True, "example": "Finance"},
                                                            "date_deadline": {"type": "string", "format": "date", "nullable": True, "example": "2026-04-15"},
                                                            "state": {"type": "string", "example": "01_in_progress"},
                                                            "user_ids": {
                                                                "type": "array",
                                                                "items": {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "id": {"type": "integer", "example": 5},
                                                                        "name": {"type": "string", "example": "Alice Johnson"},
                                                                        "login": {"type": "string", "example": "alice"},
                                                                        "avatar_url": {"type": "string", "example": "http://localhost:8069/web/image/res.users/5/avatar_128"}
                                                                    }
                                                                }
                                                            },
                                                            "create_date": {"type": "string", "format": "date-time", "nullable": True},
                                                            "write_date": {"type": "string", "format": "date-time", "nullable": True}
                                                        }
                                                    }
                                                },
                                                "meta": {
                                                    "type": "object",
                                                    "properties": {
                                                        "total": {"type": "integer", "example": 137},
                                                        "limit": {"type": "integer", "example": 50},
                                                        "offset": {"type": "integer", "example": 0}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "400": {"description": "Invalid query parameters"},
                            "401": {"description": "Missing, expired, or invalid JWT"},
                            "500": {"description": "Internal server error"}
                        },
                        "security": [{"bearerAuth": []}]
                    },
                    "post": {
                        "tags": ["Todos"],
                        "summary": "Create a Bizdom todo",
                        "description": (
                            "Creates a `project.task`. `user_ids` is a list of `res.users` ids; the creator is always "
                            "auto-added if not already present. Assignees must be active internal users (not portal). "
                            "`date_deadline` must be `YYYY-MM-DD`. Returns the fully-hydrated todo."
                        ),
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["name"],
                                        "properties": {
                                            "name": {"type": "string", "description": "Todo title (required)", "example": "Review Q1 dashboard"},
                                            "description": {"type": "string", "description": "Optional HTML/plain description", "example": "Check figures before Monday"},
                                            "pillar_id": {"type": "integer", "description": "Optional Bizdom pillar id", "example": 1},
                                            "date_deadline": {"type": "string", "format": "date", "description": "Optional deadline (YYYY-MM-DD)", "example": "2026-04-15"},
                                            "user_ids": {
                                                "type": "array",
                                                "description": "Assignees (res.users ids). Creator is always auto-included.",
                                                "items": {"type": "integer"},
                                                "example": [5, 8, 12]
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {
                            "201": {
                                "description": "Todo created",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {"type": "integer", "example": 201},
                                                "message": {"type": "string", "example": "Todo created successfully"},
                                                "data": {
                                                    "type": "object",
                                                    "properties": {
                                                        "id": {"type": "integer", "example": 42},
                                                        "name": {"type": "string", "example": "Review Q1 dashboard"},
                                                        "description": {"type": "string", "example": "Check figures before Monday"},
                                                        "pillar_id": {"type": "integer", "nullable": True, "example": 1},
                                                        "pillar_name": {"type": "string", "nullable": True, "example": "Finance"},
                                                        "date_deadline": {"type": "string", "format": "date", "nullable": True, "example": "2026-04-15"},
                                                        "state": {"type": "string", "example": "01_in_progress"},
                                                        "user_ids": {
                                                            "type": "array",
                                                            "items": {
                                                                "type": "object",
                                                                "properties": {
                                                                    "id": {"type": "integer", "example": 5},
                                                                    "name": {"type": "string", "example": "Alice Johnson"},
                                                                    "login": {"type": "string", "example": "alice"},
                                                                    "avatar_url": {"type": "string", "example": "http://localhost:8069/web/image/res.users/5/avatar_128"}
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
                            "400": {"description": "Invalid JSON, missing name, bad user_ids, or invalid date_deadline"},
                            "401": {"description": "Missing, expired, or invalid JWT"},
                            "404": {"description": "pillar_id or one of user_ids not found"},
                            "500": {"description": "Internal server error"}
                        },
                        "security": [{"bearerAuth": []}]
                    }
                },
                "/api/todos/{todo_id}": {
                    "get": {
                        "tags": ["Todos"],
                        "summary": "Get a single todo by id",
                        "description": "Returns the todo with hydrated assignees. Caller must be one of the assignees.",
                        "parameters": [
                            {
                                "name": "todo_id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer", "example": 42}
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Todo details",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {"type": "integer", "example": 200},
                                                "data": {
                                                    "type": "object",
                                                    "properties": {
                                                        "id": {"type": "integer", "example": 42},
                                                        "name": {"type": "string", "example": "Review Q1 dashboard"},
                                                        "description": {"type": "string", "example": "Check figures before Monday"},
                                                        "pillar_id": {"type": "integer", "nullable": True, "example": 1},
                                                        "pillar_name": {"type": "string", "nullable": True, "example": "Finance"},
                                                        "date_deadline": {"type": "string", "format": "date", "nullable": True, "example": "2026-04-15"},
                                                        "state": {"type": "string", "example": "01_in_progress"},
                                                        "user_ids": {
                                                            "type": "array",
                                                            "items": {
                                                                "type": "object",
                                                                "properties": {
                                                                    "id": {"type": "integer", "example": 5},
                                                                    "name": {"type": "string", "example": "Alice Johnson"},
                                                                    "login": {"type": "string", "example": "alice"},
                                                                    "avatar_url": {"type": "string", "example": "http://localhost:8069/web/image/res.users/5/avatar_128"}
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
                            "401": {"description": "Missing, expired, or invalid JWT"},
                            "403": {"description": "Forbidden - caller is not an assignee"},
                            "404": {"description": "Todo not found"},
                            "500": {"description": "Internal server error"}
                        },
                        "security": [{"bearerAuth": []}]
                    },
                    "put": {
                        "tags": ["Todos"],
                        "summary": "Update a todo (partial)",
                        "description": (
                            "Partial update: only keys present in the body are changed. "
                            "Sending `user_ids` REPLACES the entire assignee list (M2M full-set semantics). "
                            "An updated todo must still have at least one assignee."
                        ),
                        "parameters": [
                            {
                                "name": "todo_id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer", "example": 42}
                            }
                        ],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string", "example": "Review Q1 dashboard (updated)"},
                                            "description": {"type": "string", "example": "New notes"},
                                            "pillar_id": {"type": "integer", "nullable": True, "description": "Send null to clear", "example": 2},
                                            "date_deadline": {"type": "string", "format": "date", "nullable": True, "description": "Send null to clear", "example": "2026-05-01"},
                                            "user_ids": {
                                                "type": "array",
                                                "description": "Full replacement list; must contain at least one id",
                                                "items": {"type": "integer"},
                                                "example": [5, 8]
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Todo updated",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {"type": "integer", "example": 200},
                                                "message": {"type": "string", "example": "Todo updated successfully"},
                                                "data": {
                                                    "type": "object",
                                                    "properties": {
                                                        "id": {"type": "integer", "example": 42},
                                                        "name": {"type": "string", "example": "Review Q1 dashboard (updated)"},
                                                        "user_ids": {
                                                            "type": "array",
                                                            "items": {
                                                                "type": "object",
                                                                "properties": {
                                                                    "id": {"type": "integer", "example": 5},
                                                                    "name": {"type": "string", "example": "Alice Johnson"},
                                                                    "login": {"type": "string", "example": "alice"},
                                                                    "avatar_url": {"type": "string", "example": "http://localhost:8069/web/image/res.users/5/avatar_128"}
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
                            "400": {"description": "Invalid JSON body or field values"},
                            "401": {"description": "Missing, expired, or invalid JWT"},
                            "403": {"description": "Forbidden - caller is not an assignee"},
                            "404": {"description": "Todo, pillar, or user not found"},
                            "500": {"description": "Internal server error"}
                        },
                        "security": [{"bearerAuth": []}]
                    },
                    "delete": {
                        "tags": ["Todos"],
                        "summary": "Delete a todo",
                        "description": "Permanently deletes the todo. Caller must be an assignee.",
                        "parameters": [
                            {
                                "name": "todo_id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer", "example": 42}
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Todo deleted",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {"type": "integer", "example": 200},
                                                "message": {"type": "string", "example": "Todo deleted successfully"}
                                            }
                                        }
                                    }
                                }
                            },
                            "401": {"description": "Missing, expired, or invalid JWT"},
                            "403": {"description": "Forbidden - caller is not an assignee"},
                            "404": {"description": "Todo not found"},
                            "500": {"description": "Internal server error"}
                        },
                        "security": [{"bearerAuth": []}]
                    }
                },
                "/api/users": {
                    "get": {
                        "tags": ["Users"],
                        "summary": "List assignable users",
                        "description": (
                            "Returns active internal users (excludes portal/public/share users). "
                            "Used by the frontend to populate the M2M assignee picker for todos."
                        ),
                        "parameters": [
                            {
                                "name": "search",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "string", "description": "Matches name or login (ilike)"}
                            },
                            {
                                "name": "limit",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "default": 50, "maximum": 200, "example": 50}
                            },
                            {
                                "name": "offset",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "default": 0, "example": 0}
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "List of users",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "statusCode": {"type": "integer", "example": 200},
                                                "data": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "id": {"type": "integer", "example": 5},
                                                            "name": {"type": "string", "example": "Alice Johnson"},
                                                            "login": {"type": "string", "example": "alice"},
                                                            "avatar_url": {"type": "string", "example": "http://localhost:8069/web/image/res.users/5/avatar_128"}
                                                        }
                                                    }
                                                },
                                                "meta": {
                                                    "type": "object",
                                                    "properties": {
                                                        "total": {"type": "integer", "example": 137},
                                                        "limit": {"type": "integer", "example": 50},
                                                        "offset": {"type": "integer", "example": 0}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "401": {"description": "Missing, expired, or invalid JWT"},
                            "500": {"description": "Internal server error"}
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
