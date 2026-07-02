FROM node:20
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_BACKEND_URL
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
RUN npm run build
RUN mkdir -p dist/contract-ai && \
    mv dist/assets dist/contract-ai/ 2>/dev/null || true && \
    cp dist/index.html dist/contract-ai/
RUN npm install -g serve
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]