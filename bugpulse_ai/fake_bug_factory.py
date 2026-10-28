"""
BugPulse AI - Fake Bug Factory (Feature 11 & Batch Seeder)
Provides:
1. Six realistic messy single-ticket scenarios covering real-world IT maintenance failures.
2. 25-report enterprise sample batch CSV generator with deliberate duplicate clusters.
"""

import os
import pandas as pd
from typing import Dict, List, Any


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "1. Payments Java SocketTimeout (Noisy Stack + PII + Low Severity Mismatch)": {
        "title": "Payment gateway failure during checkout",
        "reported_severity": "Low",
        "reported_status": "New",
        "component": "Payments",
        "raw_text": """Reported by: Vikram Malhotra (vikram.m@fintech-client.org, Phone: +91-9845012345)
Date: 2026-10-28 09:14:22 IST
Environment: Production Cluster ap-south-1, Node: 10.240.12.88
User Aadhaar verification: 4821 9912 3041

Summary:
Checkout fails intermittently for premium credit card transactions. User was charged but order status remains PENDING.
User auth token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjdXN0XzEwOTk0MiIsImV4cCI6MTc5MzIwMDIwMCwicm9sZSI6InVzZXIifQ.K_89vX2M-aQ

To reproduce:
1. Add high-value items (>INR 10,000) to cart.
2. Select HDFC or ICICI Credit Card payment method.
3. Click 'Authorize & Pay'.
4. Spinner spins for 45 seconds, then throws 504 Gateway Timeout.

Server Exception Log:
2026-10-28 09:14:18.421 ERROR [http-nio-8443-exec-14] com.tcs.payments.gateway.StripeClient: Connection timed out connecting to https://api.payment-gateway.internal.corp:8443/v2/charges
java.net.SocketTimeoutException: Read timed out after 30000ms
\tat java.base/java.net.SocketInputStream.socketRead0(Native Method)
\tat java.base/java.net.SocketInputStream.socketRead(SocketInputStream.java:115)
\tat java.base/java.net.SocketInputStream.read(SocketInputStream.java:168)
\tat com.tcs.payments.gateway.StripeClient.executeCharge(StripeClient.java:142)
\tat com.tcs.payments.service.PaymentProcessor.processOrder(PaymentProcessor.java:88)
\tat com.tcs.payments.controller.CheckoutController.submitPayment(CheckoutController.java:64)
\tat java.base/jdk.internal.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
\tat java.base/jdk.internal.reflect.NativeMethodAccessorImpl.invoke(NativeMethodAccessorImpl.java:77)
\tat org.springframework.web.method.support.InvocableHandlerMethod.doInvoke(InvocableHandlerMethod.java:205)
2026-10-28 09:14:19.002 WARN  [http-nio-8443-exec-14] com.tcs.payments.retry.CircuitBreaker: Gateway failure count threshold exceeded (5/5). Tripping circuit to OPEN state for 60s.
2026-10-28 09:14:20.100 ERROR [http-nio-8443-exec-15] com.tcs.payments.controller.CheckoutController: Order #98412 flagged as TRANSACTION_STALLED. Dead-letter queue pinged."""
    },

    "2. Vague 1-Line UI Bug (Missing S2R, Version & Environment)": {
        "title": "Submit button not working on billing",
        "reported_severity": "High",
        "reported_status": "Assigned",
        "component": "Billing UI",
        "raw_text": """The submit button on the billing form is completely dead when I click it. Nothing happens and I cannot complete my invoice payment. Please fix this ASAP!"""
    },

    "3. Safari OAuth Login Timeout (Duplicate Cluster Member)": {
        "title": "Users cannot log in via Safari browser",
        "reported_severity": "High",
        "reported_status": "In Progress",
        "component": "Authentication",
        "raw_text": """Reported by: Priya Sharma (priya.s@corp.net) on Safari 18.2 macOS Sequoia v15.1.
App Build: v4.12.0-rc3

Steps:
1. Navigate to https://portal.enterprise-app.com/login.
2. Click 'Login with Corporate SSO (OAuth2)'.
3. Prompt redirects to Okta identity provider.
4. After entering MFA credentials, browser redirects back to callback URI https://portal.enterprise-app.com/auth/callback.

Observed Behavior:
A blank white screen displays with console error:
TypeError: null is not an object (evaluating 'window.crypto.subtle.digest')
Session cookie 'enterprise_sso_state' rejected due to SameSite=Strict cross-site POST policy.
User remains logged out with HTTP 401 Unauthorized.

Expected Behavior:
User should be redirected to Dashboard with authenticated session JWT in localStorage."""
    },

    "4. Contradictory Developer Comment Thread (UI CSS vs Redis Invalidation)": {
        "title": "Inventory count shows wrong quantity on Product Details",
        "reported_severity": "Medium",
        "reported_status": "Open",
        "component": "Catalog & Inventory",
        "raw_text": """Ticket #INV-492: Inventory count desynchronization
Reported by: QA Lead Rajesh (rajesh.k@tcs.com)
Product details page shows 15 items in stock, but adding to cart throws 'Item Out of Stock'.

--- Comment 1 (Dev A - John):
Looked at the frontend React component. Seems like a CSS or state re-render issue in ProductCounter.jsx. Will push a patch to force update.

--- Comment 2 (Dev A - John):
Pushed CSS fix in PR #204. Moving to QA.

--- Comment 3 (QA Lead Rajesh):
Tested PR #204 on staging-2. Issue STILL reproducible. It's definitely not a CSS issue.

--- Comment 4 (Backend SRE - Ananya):
Investigated database vs cache. Postgres `inventory_table` has quantity=0 for SKU-9012, but Redis key `stock:sku-9012` has cached TTL of 86400 seconds showing 15!
Root cause is a missing PubSub cache invalidation trigger when order management service completes checkout.
Do NOT touch frontend. We need to add `redisClient.del(cacheKey)` inside OrderFulfillmentConsumer.java line 112."""
    },

    "5. Silent Security IDOR Vulnerability (Marked Low - Critical P1 Mismatch)": {
        "title": "User profile endpoint URL tweak",
        "reported_severity": "Low",
        "reported_status": "New",
        "component": "User Management",
        "raw_text": """Reported by security auditor audit@thirdparty-sec.io.
Testing against API v1.4.2 in Staging environment.

Steps to reproduce:
1. Log in as regular employee user_id=10492.
2. Send GET request to /api/v1/users/10492/payroll-details with valid Bearer token.
3. Response returns personal payroll details (expected).
4. Change URL parameter to /api/v1/users/10491/payroll-details (or any other user ID).

Actual Behavior:
API returns complete unredacted salary, bank account number, and PAN card for user 10491 without checking tenant ownership or authorization boundaries.
HTTP 200 OK with full JSON payload returned.

Expected Behavior:
API must return HTTP 403 Forbidden when requesting resources belonging to another user principal."""
    },

    "6. Database Connection Pool Exhaustion (High Concurrency Outage)": {
        "title": "HikariPool-1 - Connection is not available, request timed out",
        "reported_severity": "High",
        "reported_status": "New",
        "component": "Database",
        "raw_text": """Production Incident on Database Cluster (PostgreSQL 15.4 RDS).
Timestamp: 2026-10-28 10:15:00 UTC
Traffic spiked to 2,500 req/sec during flash sale promotion.

Symptoms:
All microservices calling `OrderPlacementService` are failing with HTTP 500 Internal Server Error.

Stack Trace:
org.springframework.transaction.CannotCreateTransactionException: Could not open JDBC Connection for transaction
\tat org.springframework.jdbc.datasource.DataSourceTransactionManager.doBegin(DataSourceTransactionManager.java:309)
\tat org.springframework.transaction.support.AbstractPlatformTransactionManager.getTransaction(AbstractPlatformTransactionManager.java:380)
Caused by: java.sql.SQLTransientConnectionException: HikariPool-1 - Connection is not available, request timed out after 30005ms.
\tat com.zaxxer.hikari.pool.HikariPool.createTimeoutException(HikariPool.java:696)
\tat com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:197)
\tat com.zaxxer.hikari.HikariDataSource.getConnection(HikariDataSource.java:128)
\tat com.tcs.orders.repository.OrderRepositoryImpl.saveOrder(OrderRepositoryImpl.java:45)

Expected:
Hikari pool should scale up to maxPoolSize=50 or queue requests with graceful backpressure.
Actual:
Pool size is hardcoded to maximumPoolSize=10 in application.yml. Under high concurrent load, connections leak because unclosed ResultSets block pool threads."""
    }
}


def get_scenario_names() -> List[str]:
    """Returns list of scenario names for UI dropdown."""
    return list(SCENARIOS.keys())


def get_scenario(name: str) -> Dict[str, Any]:
    """Returns scenario data dictionary."""
    return SCENARIOS.get(name, SCENARIOS["1. Payments Java SocketTimeout (Noisy Stack + PII + Low Severity Mismatch)"])


def generate_sample_batch_csv(output_path: str = "sample_enterprise_bug_batch.csv") -> str:
    """
    Generates a realistic 25-report CSV batch containing 4 intentional duplicate clusters:
    - Cluster A (6 reports): Payments SocketTimeout / Gateway 504 Timeout
    - Cluster B (5 reports): Safari OAuth SameSite Cookie / Login failure
    - Cluster C (5 reports): Checkout Tax & Cart Calculation mismatch
    - Cluster D (4 reports): Push notification token expired / FCM failure
    - Cluster E (5 reports): Miscellaneous (Search index stale, CSS clipping, etc.)
    """
    records = [
        # Cluster A: Payments Gateway Timeouts
        {
            "bug_id": "BUG-2026-101",
            "title": "Payment gateway timeout on checkout with credit card",
            "description": "User vikram@client.com got 504 Gateway Timeout while submitting payment on node 10.140.2.19. StripeClient SocketTimeoutException after 30000ms.",
            "reported_severity": "Low",
            "reported_status": "New",
            "component": "Payments",
            "reporter_email": "vikram@client.com"
        },
        {
            "bug_id": "BUG-2026-102",
            "title": "StripeClient connection read timed out after 30000ms",
            "description": "java.net.SocketTimeoutException: Read timed out connecting to payment-gateway.internal.corp on port 8443 during submitPayment. Transaction stalled.",
            "reported_severity": "High",
            "reported_status": "Open",
            "component": "Payments",
            "reporter_email": "ops-bot@corp.net"
        },
        {
            "bug_id": "BUG-2026-103",
            "title": "Checkout order stuck in PENDING after payment gateway timeout",
            "description": "Customer was debited INR 12,500 but order remained pending due to SocketTimeoutException in PaymentProcessor.processOrder.",
            "reported_severity": "High",
            "reported_status": "In Progress",
            "component": "Payments",
            "reporter_email": "support-lead@tcs.com"
        },
        {
            "bug_id": "BUG-2026-104",
            "title": "Payment gateway circuit breaker tripped to OPEN state",
            "description": "com.tcs.payments.retry.CircuitBreaker threshold exceeded (5/5 failures). StripeClient read timeout causes 504 for all checkout users.",
            "reported_severity": "High",
            "reported_status": "New",
            "component": "Payments",
            "reporter_email": "sre-alerts@fintech.io"
        },
        {
            "bug_id": "BUG-2026-105",
            "title": "504 Gateway Timeout during credit card authorization",
            "description": "Credit card authorization endpoint fails with SocketTimeoutException on https://api.payment-gateway.internal.corp. Orders failing.",
            "reported_severity": "Medium",
            "reported_status": "New",
            "component": "Payments",
            "reporter_email": "triage-agent@tcs.com"
        },
        {
            "bug_id": "BUG-2026-106",
            "title": "Dead letter queue filled with TRANSACTION_STALLED payments",
            "description": "Payments controller dumping failed checkout requests to DLQ due to persistent 30s read timeout against backend payment gateway.",
            "reported_severity": "High",
            "reported_status": "Open",
            "component": "Payments",
            "reporter_email": "dba@fintech.io"
        },

        # Cluster B: Safari OAuth Login Failures
        {
            "bug_id": "BUG-2026-201",
            "title": "Login fails on Safari browser with blank screen",
            "description": "On Safari 18.2 macOS Sequoia, clicking Login with Corporate SSO results in a blank white screen. Console shows TypeError in subtle crypto.",
            "reported_severity": "High",
            "reported_status": "New",
            "component": "Authentication",
            "reporter_email": "priya.s@corp.net"
        },
        {
            "bug_id": "BUG-2026-202",
            "title": "Safari 18 SameSite cookie rejected on OAuth callback",
            "description": "Users on Safari cannot authenticate. Okta callback redirects to /auth/callback but session cookie is dropped due to SameSite=Strict policy.",
            "reported_severity": "High",
            "reported_status": "Open",
            "component": "Authentication",
            "reporter_email": "sec-team@corp.net"
        },
        {
            "bug_id": "BUG-2026-203",
            "title": "OAuth2 SSO callback throws 401 Unauthorized on Safari",
            "description": "Safari browser users report continuous redirect loops and 401 errors when completing MFA login on Okta portal.",
            "reported_severity": "High",
            "reported_status": "In Progress",
            "component": "Authentication",
            "reporter_email": "it-helpdesk@tcs.com"
        },
        {
            "bug_id": "BUG-2026-204",
            "title": "Mac Safari users unable to log in via SSO",
            "description": "SSO redirect fails silently on Safari 18 desktop. Cookie enterprise_sso_state missing after POST redirect.",
            "reported_severity": "Medium",
            "reported_status": "New",
            "component": "Authentication",
            "reporter_email": "qa-mac@enterprise.com"
        },
        {
            "bug_id": "BUG-2026-205",
            "title": "Authentication token missing after Safari Okta redirection",
            "description": "Browser console on Safari logs: TypeError: null is not an object (evaluating window.crypto.subtle.digest) upon callback.",
            "reported_severity": "High",
            "reported_status": "Assigned",
            "component": "Authentication",
            "reporter_email": "alex.dev@corp.net"
        },

        # Cluster C: Checkout Tax & Cart Calculation Mismatch
        {
            "bug_id": "BUG-2026-301",
            "title": "GST calculation incorrect for multi-item cart",
            "description": "When purchasing 3 items across different tax brackets (5% and 18%), cart totals round down incorrectly by 2 rupees. GST invoice mismatch.",
            "reported_severity": "Medium",
            "reported_status": "New",
            "component": "Checkout",
            "reporter_email": "finance-qa@tcs.com"
        },
        {
            "bug_id": "BUG-2026-302",
            "title": "Tax calculation discrepancy on checkout summary",
            "description": "Cart tax calculation rounds intermediate float values instead of using BigDecimal. State GST and Central GST don't sum to total tax.",
            "reported_severity": "Medium",
            "reported_status": "Open",
            "component": "Checkout",
            "reporter_email": "tax-engine@client.org"
        },
        {
            "bug_id": "BUG-2026-303",
            "title": "Rounding error in total cart amount with discount coupon",
            "description": "Applying coupon FLAT10 on 2 items causes a 1-cent rounding difference between cart total and final invoice amount.",
            "reported_severity": "Low",
            "reported_status": "New",
            "component": "Checkout",
            "reporter_email": "user-feedback@shop.in"
        },
        {
            "bug_id": "BUG-2026-304",
            "title": "Checkout invoice GST mismatch in OrderService",
            "description": "Float arithmetic in TaxCalculator.java causes precision truncation. Accounting reports discrepancies for daily reconciliation.",
            "reported_severity": "Medium",
            "reported_status": "In Progress",
            "component": "Checkout",
            "reporter_email": "audit-team@tcs.com"
        },
        {
            "bug_id": "BUG-2026-305",
            "title": "Cart total discrepancy when splitting tax lines",
            "description": "CGST + SGST line items do not equal total GST on order review page. Tax computation service rounding error.",
            "reported_severity": "Low",
            "reported_status": "New",
            "component": "Checkout",
            "reporter_email": "tester3@tcs.com"
        },

        # Cluster D: Push Notification Failures
        {
            "bug_id": "BUG-2026-401",
            "title": "FCM push notifications not received on Android 15",
            "description": "Firebase Cloud Messaging token refresh fails with 400 Bad Request on new Android 15 devices. Order status updates not received.",
            "reported_severity": "Medium",
            "reported_status": "New",
            "component": "Notifications",
            "reporter_email": "mobile-dev@app.com"
        },
        {
            "bug_id": "BUG-2026-402",
            "title": "Expired FCM device registration tokens causing notification drops",
            "description": "Notification service logs 404 UNREGISTERED_DEVICE from Google FCM endpoints. Token cleanup cron is not purging dead tokens.",
            "reported_severity": "Medium",
            "reported_status": "Open",
            "component": "Notifications",
            "reporter_email": "push-sre@corp.net"
        },
        {
            "bug_id": "BUG-2026-403",
            "title": "Android delivery push notifications timing out",
            "description": "Order dispatch notifications fail to send to delivery agents on Android app v3.8. FCM connection timeout.",
            "reported_severity": "High",
            "reported_status": "In Progress",
            "component": "Notifications",
            "reporter_email": "logistics-ops@tcs.com"
        },
        {
            "bug_id": "BUG-2026-404",
            "title": "FCM payload size limit exceeded for rich notifications",
            "description": "Push notification payload containing order item images exceeds 4KB limit. FCM rejects payload with MessageTooBigException.",
            "reported_severity": "Low",
            "reported_status": "New",
            "component": "Notifications",
            "reporter_email": "android-lead@client.com"
        },

        # Cluster E: Miscellaneous Standalone Bugs
        {
            "bug_id": "BUG-2026-501",
            "title": "Product search index stale by 2 hours",
            "description": "Elasticsearch sync cron is stalled on replica node. Newly added catalog products do not appear in keyword search.",
            "reported_severity": "Medium",
            "reported_status": "New",
            "component": "Search & Catalog",
            "reporter_email": "catalog-ops@shop.in"
        },
        {
            "bug_id": "BUG-2026-502",
            "title": "Dark mode CSS text clipping on profile page",
            "description": "User email and phone number overflow the container card when viewing user settings in Dark Mode on mobile viewport.",
            "reported_severity": "Low",
            "reported_status": "New",
            "component": "UI & Themes",
            "reporter_email": "designer@tcs.com"
        },
        {
            "bug_id": "BUG-2026-503",
            "title": "PDF invoice export throws NullPointerException when company logo missing",
            "description": "Exporting order invoice to PDF fails with 500 error if merchant profile has not uploaded a header logo image.",
            "reported_severity": "Low",
            "reported_status": "Open",
            "component": "Billing UI",
            "reporter_email": "invoice-squad@corp.net"
        },
        {
            "bug_id": "BUG-2026-504",
            "title": "Database connection pool exhausted during peak morning hours",
            "description": "HikariPool-1 connection request timed out after 30005ms in OrderPlacementService. PostgreSQL max_connections limit reached.",
            "reported_severity": "High",
            "reported_status": "New",
            "component": "Database",
            "reporter_email": "dba-oncall@tcs.com"
        },
        {
            "bug_id": "BUG-2026-505",
            "title": "IDOR vulnerability in payroll endpoint returns other user records",
            "description": "GET /api/v1/users/{id}/payroll-details does not validate user principal against requested resource ID. Critical data leak.",
            "reported_severity": "Low",
            "reported_status": "New",
            "component": "User Management",
            "reporter_email": "sec-audit@fintech.io"
        }
    ]

    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    path = generate_sample_batch_csv()
    print(f"Generated sample batch CSV at {path}")

