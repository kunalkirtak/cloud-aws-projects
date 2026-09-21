# EC2 Security Group Configuration

This document describes the recommended Security Group rules for
deploying the AWS EC2 AI Chatbot to a single EC2 instance for learning
and portfolio purposes.

## Inbound Rules

| Purpose            | Protocol | Port | Source                     |
|--------------------|----------|------|-----------------------------|
| SSH access         | TCP      | 22   | My IP only (not 0.0.0.0/0)  |
| Application (temp) | TCP      | 8000 | My IP only (temporary testing) |

## Why not `0.0.0.0/0` for SSH?

`0.0.0.0/0` allows connections from *any* IPv4 address on the internet.
Opening port 22 to the entire internet exposes the instance to
constant automated login attempts and brute-force scanning. Restricting
the SSH rule to "My IP" (or a small, known set of IPs) drastically
reduces the attack surface. If your IP address changes, update the
Security Group rule rather than widening it to `0.0.0.0/0`.

## Why restrict port 8000 as well?

Port 8000 in this project is used to reach the FastAPI application
directly via Uvicorn during testing. Leaving an application port open
to the entire internet is not appropriate for production traffic and
is only acceptable here as a temporary, narrowly-scoped convenience
for manual verification during learning/demo use.

## Production Guidance

For anything beyond a learning/demo deployment:

* Do not expose Uvicorn directly to the internet. Put a reverse proxy
  (such as Nginx) or a load balancer (such as an Application Load
  Balancer) in front of it.
* Serve traffic over HTTPS using a certificate (for example, via
  AWS Certificate Manager with an ALB, or Let's Encrypt with Nginx).
* Scope Security Group rules as narrowly as possible, and review them
  periodically.

## Outbound Rules

The default outbound rule (allow all outbound traffic) is generally
acceptable for this project, since the application does not require
restrictive egress control to function locally in this learning
setup.
