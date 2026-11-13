from prometheus_client import Counter, Histogram

# 1. Count all HTTP request
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"]
)

# 2. Measure HTTP request duration
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request processing duration in seconds",
    ["method", "endpoint"]
)

# 3. Count HTTP errors

HTTP_ERRORS_TOTAL = Counter(
    "http_errors",
    "Total number of HTTP error responses",
    ["method", "endpoint", "status"]
)