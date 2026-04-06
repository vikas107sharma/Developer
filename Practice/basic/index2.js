const order = {
  shipments: [
    {
      shipmentId: 1,
      warehouse: "BLR",
      items: [
        { sku: "DOG", qty: 2 },
        { sku: "CAT", qty: 1 }
      ],
      status: "created"
    },
    {
      shipmentId: 2,
      warehouse: "BLR",
      items: [
        { sku: "BIRD", qty: 3 }
      ],
      status: "created"
    },
    {
      shipmentId: 3,
      warehouse: "BLR",
      items: [],
      status: "created"
    }
  ]
};

function isWarehouseMatch(shipment, deliveryNote) {
  return shipment.warehouse == deliveryNote.warehouse
}

function isItemsMatch(shipment, deliveryNote) {
  // Match shipment.skus and deliverynote.skus and quantity also

  if(shipment.items.length() != deliveryNote.items.length()) return false;
 
}

function isMatch(shipment, deliveryNote) {
   return isWarehouseMatch(shipment, deliveryNote) && isItemsMatch()
}

function reconcileDeliveryNotes(order, deliveryNote) {
    for (const shipment of order.shipments) {
      if(isMatch(shipment, deliveryNote)) {

      }
    }
}

(()=>{
    const cancelled_dn = {
                            dnId: "DN-C1",
                            warehouse: "BLR",
                            cancelled: true,
                            items: [
                                { sku: "DOG", qty: 2 },
                                { sku: "CAT", qty: 1 }
                            ]
                        }
    const cancelled_dn_result =  reconcileDeliveryNotes(order, cancelled_dn);
    console.log(cancelled_dn_result, '\n \n')
})()