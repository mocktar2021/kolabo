# Build the SPA, then serve the static output. Two stages so node and the
# 300 MB of node_modules never reach the running container — the image that
# ships is nginx plus a few hundred KB of assets.

FROM node:20-alpine AS build
WORKDIR /app

# THE API URL IS BAKED IN AT BUILD TIME, NOT READ AT RUNTIME. Vite substitutes
# import.meta.env.* into the bundle during `vite build`, so there is no process
# environment left to read when the browser runs it. That means rebuilding the
# image is the only way to repoint the web app at a different API — which is
# worth knowing before someone spends an afternoon setting a runtime env var
# and wondering why the app still calls localhost:8000.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

COPY package.json package-lock.json* ./
# `npm ci` when there is a lockfile, `npm install` when there is not. The repo
# does not commit one today; this keeps the build reproducible the moment it
# does without needing another edit here.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
# `npm run build` is `tsc && vite build`, so a type error fails the image
# build rather than shipping a broken bundle.
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
