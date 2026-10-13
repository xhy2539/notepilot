FROM node:22-bookworm AS ui
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY backend/ /app/backend/
RUN pip install --no-cache-dir -e /app/backend && python -m playwright install --with-deps chromium
COPY --from=ui /app/frontend/dist /app/frontend/dist
COPY --from=ui /app/frontend/node_modules/@fontsource/noto-sans-sc /app/frontend/node_modules/@fontsource/noto-sans-sc
ENV NOTEPILOT_DATA=/app/data
EXPOSE 8000
CMD ["uvicorn", "notepilot.app:app", "--host", "0.0.0.0", "--port", "8000"]
