Good question — this is basically “when if/else stops being manageable”.

Right now you have:

dimension 1 → platform (web/app)


So code is simple:

if (platform === 'web') sendWeb()
else sendApp()


Totally fine.

What Level-3 Complexity Means

When notification behavior depends on 3 or more independent decision axes.

Example axes:

1) Platform        → web / app / ios
2) Notification type → payment / order / chat / alert
3) Priority        → normal / critical
4) Delivery channel → push / email / sms fallback
5) User preference → mute / business-hours / realtime


Now combinations explode.

Realistic Example (your system after few features)

You add:

payment notification

order assigned notification

chat message

critical stock alert

fallback SMS if app offline

Now your code becomes:

if (platform === 'web' && type === 'payment') { ... }
else if (platform === 'app' && type === 'payment') { ... }
else if (platform === 'app' && type === 'chat') { ... }
else if (platform === 'web' && type === 'chat') { ... }
else if (type === 'critical' && !userActive) sendSMS()
else if (priority === 'low') delaySend()
else if (userMuted) skip()


This is Level-3 complexity.

You now have:

platform × type × rules = exponential branching


At this point:

Bugs become invisible

Adding 1 feature breaks 3

Testing becomes impossible

How Strategy fixes it (example)

Instead of branching:

Pick behavior object based on context

const handler = NotificationResolver.resolve({
  platform,
  type,
  priority
});

await handler.send(payload);


Now each combination lives in its own small unit.

Quick Rule of Thumb
Condition Count	Action
1–2 if conditions	keep simple if/else
3–5 nested business rules	refactor service
3+ independent dimensions	Strategy pattern
Fallback channels	definitely Strategy
Concrete trigger in your project

The day you add:

“If payment fails → push
If not delivered in 30 sec → SMS
If salesman offline → notify officer”

You must move to Strategy.

Final meaning

Level-3 = when behavior depends on multiple independent business factors, not just platform.

You’re currently Level-1 → stay simple.