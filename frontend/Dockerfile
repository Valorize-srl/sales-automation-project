FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

RUN npm run build

EXPOSE ${PORT:-3000}

CMD sh -c "npm run start -- -p ${PORT:-3000}"
