# Builds and runs NanoVox as the one process it is meant to be: the API and
# the built frontend, on one port. Two stages exist only because the frontend
# needs Node to build and the backend needs Python to run — the built output
# is the only thing that crosses from one stage to the other.

# --- Stage 1: build the frontend -------------------------------------------
FROM node:20-slim AS frontend-build
WORKDIR /app/Code/Frontend
# Dependencies first, so an application-code change does not invalidate this
# layer and force a full npm ci on every build.
COPY Code/Frontend/package.json Code/Frontend/package-lock.json ./
RUN npm ci
COPY Code/Frontend/ ./
RUN npm run build

# --- Stage 2: the backend, serving that build -------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app

COPY Code/Backend/requirements.txt Code/Backend/requirements.txt
RUN pip install --no-cache-dir -r Code/Backend/requirements.txt

COPY Code/Backend/ Code/Backend/
COPY --from=frontend-build /app/Code/Frontend/dist Code/Frontend/dist

ENV APP_ENV=prod
WORKDIR /app/Code/Backend

# Render (and most host-provided-port platforms) inject PORT at runtime;
# 8000 is only the fallback for a plain `docker run` with none set.
ENV PORT=8000
EXPOSE 8000

# Migrating on every boot is what makes "push a new revision" the whole
# deploy story — no separate manual migration step to forget. Each migration
# here is already written to be a no-op when there is nothing for it to do.
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn frameworks_drivers.main:app --host 0.0.0.0 --port ${PORT}"]
