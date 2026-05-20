# Data Models — SmartCity Platform

This file documents the shape of every document stored in MongoDB.
The four NoSQL databases (MongoDB, Neo4j, Redis, Elasticsearch) each
keep their own slice of this data; the canonical shape lives here.

---

## User
Auth-only record. One per registered account.

```js
User {
  _id,
  username,
  email,
  passwordHash,
  role,           // "citizen" | "technician" | "manager"
  citizenId,      // optional, links to Citizen._id
  technicianId,   // optional, links to Technician._id
  createdAt
}
```

## Citizen
Civic profile for a person. Created during registration.

```js
Citizen {
  _id,
  nationalId,
  name,
  email,
  phone,
  area: {
    areaId,
    areaName
  },
  civicScore,
  language,
  notificationPreference,
  createdAt
}
```

## ServiceRequest
The main collection — one document per reported issue.

```js
ServiceRequest {
  _id,
  citizen: {
    citizenId,
    citizenName
  },
  category,
  subCategory,
  description,
  location: {
    gpsCoordinate,   // GeoJSON Point: { type, coordinates: [lng, lat] }
    areaId,
    areaName,
    areaDescription
  },
  status,           // "pending" | "assigned" | "in_progress" | "resolved"
  priority,         // "low" | "medium" | "high"
  assignment: {
    departmentId,
    departmentName,
    technicianId,
    technicianName
  },
  timestamps: {
    createdAt,
    assignedAt,
    resolvedAt
  },
  photoUrls: [],
  satisfactionRate,
  createdAt,
  updatedAt
}
```

## Area
Reference data — city districts.

```js
Area {
  _id,
  name,
  boundaryPolygon,
  population
}
```

## Department
Reference data — city departments and the categories they handle.

```js
Department {
  _id,
  name,
  contactEmail,
  contactPhone,
  serviceCategories: [],   // e.g. ["waste", "infrastructure"]
  areas: []                // area IDs the dept covers
}
```

## Technician
Field worker assigned to a department.

```js
Technician {
  _id,
  name,
  departmentId,
  departmentName,
  resolvedCount,
  activeRequestIds: [],
  createdAt
}
```

## Category
Issue taxonomy (category + sub-categories + default priority).

```js
Category {
  _id,
  name,
  defaultPriority,
  subCategories: []
}
```
