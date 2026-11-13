Hi!
Thank you for coming to take a look at the final project we developed for a 5-week course on bio-inspired algorithms. 

This is a web-app that uses the Ant Colony Optimization (ACO) algorithm for the Vehicle Routing Problem with time windows and capacity limits for DHL branches in Querétaro. 
We use an API to realistically get the time each vehicle type would spend delivering the packages. 
We also automatically consider adding more shifts as capacity grows beyond what one driver can cover in an 8-hour shift. 

However, note we don't include a baseline to compare the route optimality to. 
This is because it went beyond course scope, but it is on my radar and I do want to update it eventually; beyond optimality the main feature is that you can get a good-enough optimal route with few calculations that run faster than traditional solvers for last-mile problems. 
My goal is to eventually add a deterministic optimizer like Dijkstra's algorithm as a baseline, but to compare the resources needed to reach both routes. 

The prompt for the class project was to show an application of a bio-inspired algorithm of our choice. Please forgive the messy structure and missing features, we were mainly focused on how the final web-app worked (and looked). 

**This project was recognized and therefore presented at ITESM's bi-annual engineering fair; where we got to show our work to industry leaders, professors and students. **
