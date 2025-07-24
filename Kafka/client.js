const { Kafka } = require("kafkajs");

const kafka = new Kafka({
    clientId: 'my_app',
    brokers: ['http://192.168.1.102:2181'],
})

module.exports = {
  kafka,
};