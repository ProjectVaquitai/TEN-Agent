#!/bin/bash

cat << EOF | mongosh
try {
  print("[Step 1] Creating admin user...");
  db = db.getSiblingDB("admin");
  
  if (!db.getUser("$MONGO_INITDB_ROOT_USERNAME")) {
    db.createUser({
      user: "$MONGO_INITDB_ROOT_USERNAME",
      pwd: "$MONGO_INITDB_ROOT_PASSWORD",
      roles: [
        { role: "userAdminAnyDatabase", db: "admin" },
        { role: "readWriteAnyDatabase", db: "admin" },
        { role: "dbAdminAnyDatabase", db: "admin" }
      ]
    });
    print("✅ Admin user created successfully");
  } else {
    print("ℹ️ Admin user already exists");
  }

  print("\n[Step 2] Switching to application database...");
  db = db.getSiblingDB("$MONGO_INITDB_DATABASE");
  print("✅ Switched to ${MONGO_INITDB_DATABASE}");

  print("\n[Step 3] Creating collections...");
  if (!db.getCollectionNames().includes("users")) {
    db.createCollection("users");
    print("✅ Users collection created");
  }
  if (!db.getCollectionNames().includes("sessions")) {
    db.createCollection("sessions");
    print("✅ Sessions collection created");
  }

  print("\n[Step 4] Creating indexes...");
  db.users.createIndex({ "email": 1 }, { unique: true });
  db.sessions.createIndex({ "createdAt": 1 }, { expireAfterSeconds: 86400 });
  print("✅ Indexes created");

  print("\n[Step 5] Verifying setup...");
  var collections = db.getCollectionNames();
  if (collections.includes("users") && collections.includes("sessions")) {
    print("✅ All collections verified");
    printjson(collections);
  } else {
    throw new Error("Collections verification failed");
  }

} catch(err) {
  print("❌ Error during initialization:");
  printjson(err);
  quit(1);
}
EOF