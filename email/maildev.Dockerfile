FROM node:17-alpine
RUN npm install -g maildev
CMD maildev --smtp 25 --web 80 --incoming-user test --incoming-pass test
