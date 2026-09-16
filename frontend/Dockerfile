FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .

# NEXT_PUBLIC_* wird von Next.js in das Client-Bundle eingebaut, und die
# next.config.js-Rewrites (BACKEND_INTERNAL_URL) werden ebenfalls beim Build
# aufgeloest - beide Werte muessen daher bereits hier als Build-Argumente
# vorliegen, nicht erst als Laufzeit-Umgebungsvariable.
ARG NEXT_PUBLIC_API_BASE_URL=http://backend:8000
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["npm", "start"]
