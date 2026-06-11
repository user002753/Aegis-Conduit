"""Resource optimizer with OR-Tools VRP fallback.

This module attempts to use OR-Tools to solve a simple capacitated
vehicle routing problem (CVRP). If OR-Tools is not available, it
falls back to a greedy assignment.
"""
from __future__ import annotations

from typing import List, Dict, Any, Tuple
import math

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    _HAS_ORTOOLS = True
except Exception:
    _HAS_ORTOOLS = False


class ResourceOptimizer:
    def __init__(self):
        pass

    def assign(self, vehicles: List[Dict[str, Any]], demands: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        """Simple compatibility wrapper: prefer OR-Tools if available.

        vehicles: list of dicts, each with at least `id` and optional `capacity`.
        demands: list of dicts, each with at least `id` and `demand` (int).

        Returns a list of (vehicle_id, demand_id) assignments.
        """
        if _HAS_ORTOOLS:
            try:
                return self._solve_vrp_ortools(vehicles, demands)
            except Exception:
                pass

        # fallback: deterministic first-fit assignment with vehicle capacities.
        assignments: List[Tuple[str, str]] = []
        remaining = [int(v.get("capacity", 100)) for v in vehicles]
        for d in demands:
            demand_size = int(d.get("demand", 1))
            for vi, v in enumerate(vehicles):
                if remaining[vi] >= demand_size:
                    assignments.append((v.get("id", f"veh{vi}"), d.get("id", "dem")))
                    remaining[vi] -= demand_size
                    break
        return assignments

    def _solve_vrp_ortools(self, vehicles: List[Dict[str, Any]], demands: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        # Build a trivial distance matrix: use index distance (demo only).
        n = len(demands) + 1  # depot + demands
        dist_matrix = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                dist_matrix[i][j] = abs(i - j)

        demands_values = [0] + [int(d.get("demand", 1)) for d in demands]
        vehicle_capacities = [int(v.get("capacity", 100)) for v in vehicles]
        num_vehicles = len(vehicles)

        manager = pywrapcp.RoutingIndexManager(len(dist_matrix), num_vehicles, 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return dist_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        def demand_callback(from_index):
            node = manager.IndexToNode(from_index)
            return demands_values[node]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # null capacity slack
            vehicle_capacities,
            True,
            "Capacity",
        )

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        search_params.time_limit.seconds = 5

        solution = routing.SolveWithParameters(search_params)
        assignments: List[Tuple[str, str]] = []
        if solution:
            for vehicle_id in range(num_vehicles):
                index = routing.Start(vehicle_id)
                route = []
                while not routing.IsEnd(index):
                    node = manager.IndexToNode(index)
                    if node != 0:
                        route.append(node - 1)
                    index = solution.Value(routing.NextVar(index))
                # assign demands in route to this vehicle
                for dem_idx in route:
                    assignments.append((vehicles[vehicle_id].get("id", f"veh{vehicle_id}"), demands[dem_idx].get("id", f"dem{dem_idx}")))
        else:
            # fallback to greedy
            for i, d in enumerate(demands):
                v = vehicles[i % len(vehicles)]
                assignments.append((v.get("id", f"veh{i}"), d.get("id", f"dem{i}")))

        return assignments
