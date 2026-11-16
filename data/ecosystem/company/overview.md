# Demo Studio: portfolio overview

Demo Studio is an invented software studio. It builds and operates applications for its clients, and every client has its own product vision. This page gives the company-wide picture.

## Clients and applications

| Client | Application | What it is | Services |
|---|---|---|---|
| Demo Grocery | Storefront | The online store where customers buy groceries | `catalog-service`, `orders-service`, `payments-service`, `notifications-service` |
| Demo Logistics | Fleet Tracker | The dashboard and backend that follow vehicles and plan routes | `tracking-service`, `routing-service` |
| Demo Logistics | Driver App | The mobile experience used by drivers on the road | `driver-service` |

## How the clients differ

- **Demo Grocery** cares about a reliable checkout: a failed payment must not lose the order. Its product owner is Sofía Mendoza.
- **Demo Logistics** cares about visibility and punctuality: dispatchers must see where every vehicle is, and drivers must receive routes that hold up. Its product owner is Camila Ortega.

Each client's vision and feature catalog live under `clients/<client>/product/`. The services of an application are described in their own folders under `repos/`, and every service says which client and application it belongs to.

## Working agreements

- A service belongs to exactly one application, and an application to exactly one client.
- Services communicate through APIs and events; no service of one client calls a service of another.
- Documentation lives next to the code of each service and is the source of truth for the knowledge assistant.
