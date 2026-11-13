import logging
import time
from django.conf import settings
import uuid
from contextvars import ContextVar
from django.db import connection
from django.urls import resolve, Resolver404
from config.metrics import (
    HTTP_ERRORS_TOTAL,
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION
)

logger = logging.getLogger(__name__)

request_id_context = ContextVar(
    "request_id",
    default="-"
)

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_context.get()
        return True

class RequestLoggingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

        self.slow_threshold = getattr(
            settings,
            "SLOW_REQUEST_THRESHOLD_MS",
            1000
        )

    def __call__(self, request):
        # generate a unique ID for this request
        request_id = str(uuid.uuid4())

        # store it in the curreny execution context
        token = request_id_context.set(request_id)

        request.request_id = request_id

        # default values incase request processing raises an exception
        status_code = 500
        endpoint = "unmatched"

        # Record when the request starts
        start_time = time.perf_counter()

        query_metrics = {
            "count": 0,
            "slow_count": 0,
        }

        def query_monitoring_wrapper(
                execute,
                sql,
                params,
                many,
                context
        ):
            query_start = time.perf_counter()

            try:
                return execute(sql, params, many, context)
            finally:
                query_duration = (
                    time.perf_counter() - query_start
                ) * 1000
                query_duration = round(query_duration, 2)
                query_metrics["count"] += 1

                threshold = getattr(
                    settings,
                    "SLOW_DATABASE_QUERY_THRESHOLD_MS",
                    100
                )

                if query_duration >= threshold:
                    query_metrics["slow_count"] += 1
                    # log the sql operation type, not sql parameters

                    operation = sql.strip().split(" ", 1)[0].upper()

                    logger.warning(
                        "SLOW DATABASE QUERY: request_id=%s "
                        "operation=%s duration_ms=%s",
                        request_id,
                        operation,
                        query_duration
                    )

        #process the request and get the response
        try:
            with connection.execute_wrapper(query_monitoring_wrapper):
                response = self.get_response(request)

                # capture the actual response status
                status_code = response.status_code

                # Resolve the url pattern to avoid high-cardinality labels

                try:
                    match = resolve(request.path_info)
                    endpoint = match.route or match.view_name or "unknown"
                except Resolver404:
                    endpoint = "unmatched"

            # calculate request processing duration

            duration = time.perf_counter() - start_time

            duration_ms = round(duration * 1000, 2)

            # common request information

            log_message = (
                "HTTP request: request_id=%s "
                "method = %s path=%s status=%s "
                "duration_ms=%s query_count=%s "
                "slow_query_count=%s"
            )

            log_arguments = (
                request_id,
                request.method,
                request.path,
                response.status_code,
                duration_ms,
                query_metrics["count"],
                query_metrics["slow_count"]
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
            response["X-Request-ID"] = request_id

            return response
        finally:
            # Calculate total requests duration
            duration = time.perf_counter() - start_time

            #1. Count HTTP requests
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=endpoint,
                status=str(status_code)
            ).inc()

            #2. Record request duration
            HTTP_REQUEST_DURATION.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(duration)

            # 3. Count HTTP errors

            if status_code >= 400:
                HTTP_ERRORS_TOTAL.labels(
                    method=request.method,
                    endpoint=endpoint,
                    status=str(status_code)
                ).inc()
            # prevent request IDs leaking into other requests

            request_id_context.reset(token)
