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

# The Google sign in client id, and it gets the identical treatment for the
# identical reason. A VITE_ variable that reaches the container's environment
# but not this ARG is not "missing at runtime", it is absent from the bundle
# entirely: the code reads import.meta.env.VITE_GOOGLE_CLIENT_ID, vite
# substitutes whatever was set HERE, at build time, and an unset one compiles
# to an empty string.
#
# WHICH IS A SILENT FAILURE, NOT A LOUD ONE. Empty is a state the app is
# written to handle: web/src/lib/googleSignIn.ts reports the provider absent
# and the button does not render at all, which is correct behaviour for a
# deployment that has no client id and is indistinguishable from a deployment
# that has one in the wrong place. Nothing errors, nothing is logged, and the
# button is simply not there.
#
# NOT A SECRET. An OAuth client id is public by construction, it travels in
# every token request the browser makes, and there is no client secret beside
# it because this flow posts an ID token and the server only reads it. Baking
# it into a bundle is what Google's own documentation has you do.
ARG VITE_GOOGLE_CLIENT_ID
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

# Which deployment this bundle is for, and it is NOT a new setting: compose
# feeds it from the ENV already in deploy/.env, which preflight-env.sh already
# refuses to leave empty or set to anything but development or production. One
# value per box rather than two that can disagree about what the box is.
#
# UNSET IS SAFE HERE, unlike the two above, and in the opposite direction.
# Empty compiles to a value that is not "production", so the banner appears.
# Getting this wrong makes a site say it is development when it is not, which
# somebody notices immediately; the failure worth preventing is the silent one
# in the other direction. See web/src/lib/env.ts.
ARG VITE_KOLABO_ENV
ENV VITE_KOLABO_ENV=$VITE_KOLABO_ENV

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

# robots.txt is written here rather than committed under web/public/, because
# the right answer differs per environment and vite copies public/ verbatim
# into every build: one committed file would say the same thing on both boxes.
#
# ARG IS REDECLARED BECAUSE ARG SCOPE IS PER STAGE. The one above belongs to
# the build stage and is not visible here, so leaving this line out would make
# the `if` below always take the development branch, silently.
#
# It is served because it is a real file: nginx.conf tries $uri before falling
# back to index.html, so this is answered directly rather than by the SPA.
ARG VITE_KOLABO_ENV
RUN if [ "$VITE_KOLABO_ENV" = "production" ]; then \
      printf 'User-agent: *\nAllow: /\n' > /usr/share/nginx/html/robots.txt; \
    else \
      printf 'User-agent: *\nDisallow: /\n' > /usr/share/nginx/html/robots.txt; \
    fi

EXPOSE 80
