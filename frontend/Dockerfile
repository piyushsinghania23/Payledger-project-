FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 3000

ENV REACT_APP_API_URL=http://localhost:8000/api/v1

CMD ["npm", "start"]
