FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps

COPY . .

EXPOSE 4200

ENTRYPOINT ["npx", "concurrently", "-k", "-n", "tailwind,angular", "npm:tailwind:watch", "npx ng serve --host 0.0.0.0 --port 4200 --poll 2000"]
