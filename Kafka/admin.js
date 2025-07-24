const { kafka } = require("./client.js");

async function init() {
  const admin = kafka.admin;
  console.log("Admin connecting...");
  admin.connect();
  console.log("Admin connecting success");

  console.log("Creating topic rider-update...");
  await admin.createTopics({
    topics: [
      {
        topic: "rider-update",
        numPartitions: 2,
      },
    ],
  });
  console.log("Topic created rider-update");

  console.log("Disconnecting admin");
  await admin.disconnect();
}

init();
