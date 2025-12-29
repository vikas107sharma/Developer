export const database = {
  "users": [
    {
      "id": "u1",
      "name": "Vikas Sharma",
      "email": "vikas@example.com",
      "role": "user"
    },
    {
      "id": "u2",
      "name": "Amit Kumar",
      "email": "amit@example.com",
      "role": "admin"
    }
  ],

  "products": [
    {
      "id": "p1",
      "name": "Laptop",
      "price": 70000,
      "stock": 5
    },
    {
      "id": "p2",
      "name": "Keyboard",
      "price": 2000,
      "stock": 20
    }
  ],

  "orders": [
    {
      "id": "o1",
      "userId": "u1",
      "productId": "p1",
      "status": "PENDING"
    }
  ],

  "payments": [
    {
      "id": "pay1",
      "orderId": "o1",
      "amount": 70000,
      "status": "SUCCESS"
    }
  ]
}
