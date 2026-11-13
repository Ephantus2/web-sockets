import logging
import time
from django.conf import settings

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

        self.slow_threshold = getattr(
            settings,
            "SLOW_REQUEST_THRESHOLD_MS",
            1000
        )

    def __call__(self, request):
        # Record when the request starts
        start_time = time.perf_counter()

        #process the request and get the response

        response = self.get_response(request)

        # calculate request processing duration

        duration = time.perf_counter() - start_time

        duration_ms = round(duration * 1000, 2)

        # common request information

        log_message = (
            "HTTP request: method=%s path=%s "
            "status=%s duration_ms=%s"
        )

        log_arguments = (
            request.method,
            request.path,
            response.status_code,
            duration_ms
        )

        # Detect slow requests
        if duration_ms >= self.slow_threshold:
            logger.warning(
                "SLOW REQUEST: " + log_message,
                *log_arguments
            )
        else:
            logger.info(
                log_message,
                *log_arguments
            )

        # Expose processing time to the client
        response["X-Response-Time-ms"] = str(duration_ms)

        return response