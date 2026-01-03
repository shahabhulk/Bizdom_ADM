from odoo import http


class BizdomOnlineDashboard(http.Controller):
    """
    Controller for serving HTML pages for bizdom_online public dashboards.
    
    Note: API endpoints have been moved to use existing APIs:
    - Dashboard API: /api/dashboard (from bizdom module) with favoritesOnly=true
    - Score API: /api/score/overview (from bizdom module)
    """

    @http.route('/bizdom/dashboard/public', type='http', auth='public', sitemap=False)
    def public_dashboard_page(self, **kw):
        """
        Public dashboard page (no login required)
        Accessible at: http://localhost:8070/bizdom/dashboard/public
        """
        html_content = """<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title>Bizdom Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"/>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet"/>
    </head>
    <body>
        <div id="bizdom-public-dashboard-app">
            <div class="container-fluid p-0">
                <!-- Loading indicator -->
                <div id="loading-indicator" class="text-center p-5" style="min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #f5f7fa;">
                    <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-3" style="color: #6c757d; font-size: 1.1rem;">Loading dashboard...</p>
                </div>
                
                <!-- Dashboard content will be injected here -->
                <div id="dashboard-content" style="display: none;"></div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script src="/bizdom_online/static/src/js/dashboard_public.js" defer></script>
    </body>
</html>"""
        
        return http.Response(html_content, content_type='text/html;charset=utf-8')

    @http.route('/bizdom/score/dashboard', type='http', auth='public', sitemap=False)
    def score_dashboard_page(self, **kw):
        """
        Score dashboard page (JWT authentication required via JavaScript)
        Accessible at: http://localhost:8070/bizdom/score/dashboard?scoreId=1&scoreName=TAT
        """
        html_content = """<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title>Score Dashboard - Bizdom</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"/>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet"/>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    </head>
    <body>
        <div id="bizdom-score-dashboard-app">
            <div class="container-fluid p-0">
                <!-- Loading indicator -->
                <div id="loading-indicator" class="text-center p-5" style="min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #f5f7fa;">
                    <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-3" style="color: #6c757d; font-size: 1.1rem;">Loading score dashboard...</p>
                </div>
                
                <!-- Dashboard content will be injected here -->
                <div id="score-dashboard-content" style="display: none;"></div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script src="/web/static/lib/Chart/Chart.min.js"></script>
        <script src="/bizdom_online/static/src/js/score_dashboard_public.js" defer></script>
    </body>
</html>"""
        
        return http.Response(html_content, content_type='text/html;charset=utf-8')


