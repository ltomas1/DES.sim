from mosaik_components.heatpump.hotwatertank.hotwatertank_mosaik import (
    HotWaterTankSimulator as _UpstreamSim,
    set_nested_attr
)
from mosaik_components.heatpump.hotwatertank.hotwatertank import MassFlow

class HotWaterTankSimulator(_UpstreamSim):
    """Subclass that fixes the substep energy-balance bug in upstream.

    Upstream HotWaterTankSimulator.step() calls model.step() directly,
    which triggers the tank's internal recursive substep fallback and
    mismanages _T_buffer. Here we override step() to route through
    _step_model(), which pre-computes substeps and handles _T_buffer
    correctly.

    Vendored from upstream: <version 1.0.1>
    Reason: substep _T_buffer bug, pending upstream merge request.
    """

    def _compute_n_substeps(self, model, step_size):
        """
        Mirror the exact CFL check from HotWaterTank.step():
        1. Assign connection flows to their corresponding layers (as massflows)
        2. Check per-layer inflow/outflow against layer volume
        3. Compute the required number of sub-steps
        4. Clean up the temporary massflows again
        """

        # Step 1: assign connection flows to layers (same as model.step())
        for key, connection in model.connections.items():
            try:
                if connection.F > 0:
                    if connection.T is not None:
                        connection.corresponding_layer.add_massflow(
                            MassFlow(connection.F, connection.T))
                else:
                    connection.corresponding_layer.add_massflow(
                        MassFlow(connection.F, connection.T))
            except TypeError:
                pass

        # Step 2: compute V_factors exactly as model.step() does
        V_factors = []
        for idx, layer in enumerate(model.layers):
            V_in = layer.inflow * step_size
            V_out = abs(layer.outflow * step_size)
            V = max(V_in, V_out)
            if V > layer.volume:
                V_factors.append(V // layer.volume + (V % layer.volume > 0))

        # Step 3: clean up temporary massflows
        for layer in model.layers:
            layer.empty_massflows()

        return int(max(V_factors)) if V_factors else 1

    def _step_model(self, model, step_size):
        """
        Execute one physical step, handling CFL violations via sub-stepping
        so that Mosaik always sees a fixed step size.

        We pre-compute the required number of sub-steps using the exact same
        layer inflow/outflow logic as HotWaterTank.step(), then call
        model.step() with the already-safe sub-step size. This prevents
        model.step() from ever entering its own recursive fallback, which
        is what was causing the energy balance drift.
        """
        n_substeps = self._compute_n_substeps(model, step_size)

        if n_substeps == 1:
            model.step(step_size)
        else:
            sub_dt = step_size / n_substeps
            # Clear _T_buffer for all connections before substepping so every
            # substep contributes its outflow temperature to the average.
            for conn in model.connections.values():
                conn._T_buffer = []
            for _ in range(n_substeps):
                model.step(sub_dt, adapted_step_size_mode=True)
    
    def step(self, time, inputs, max_advance):
        if self.meta['type'] == 'event-based':
            if self.time != time:
                self.first_iteration = True
                self.step_executed = False
            else:
                self.first_iteration = False
            self.time = time
        for eid, attrs in inputs.items():
            for attr, src_ids in attrs.items():
                if attr == '_':
                    pass
                else:
                    for src_id, val in src_ids.items():
                        set_nested_attr(self.models[eid], attr, val)
        if self.meta['type'] == 'event-based':
            if not self.first_iteration and not self.step_executed:
                for eid, model in self.models.items():
                    self._step_model(model, self.step_size)  # <-- changed
                    self.step_executed = True
        else:
            for eid, model in self.models.items():
                self._step_model(model, self.step_size)      # <-- changed
        if self.meta['type'] == 'event-based':
            if self.step_executed and (time + self.step_size) <= self.mosaik.world.until:
                return (time + self.step_size)
        else:
            return (time + self.step_size)

