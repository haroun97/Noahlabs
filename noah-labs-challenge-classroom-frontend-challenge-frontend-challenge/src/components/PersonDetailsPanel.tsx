import { Alert, CircularProgress, Stack, Typography } from "@mui/material";
import type { PersonDetailsState, PersonRef } from "../hooks/usePersonDetails";
import { PersonDetails } from "./PersonDetails";

type PersonDetailsPanelProps = {
	state: PersonDetailsState;
};

function formatPersonLabel(person: PersonRef): string {
	return `${person.displayName} (ID ${person.id})`;
}

// Presentational container: it owns no async logic, it just maps each state of
// the discriminated union to its UI. The exhaustive switch means adding a new
// state to the union becomes a compile error here until it is handled.
export function PersonDetailsPanel({ state }: PersonDetailsPanelProps) {
	switch (state.status) {
		case "idle":
			return (
				<Typography color="text.secondary">
					Select a person to view their details.
				</Typography>
			);
		case "loading":
			return (
				<Stack
					direction="row"
					alignItems="center"
					gap={1}
					aria-live="polite"
					aria-busy="true"
				>
					<CircularProgress size={20} aria-hidden />
					<Typography color="text.secondary">
						Loading details for {formatPersonLabel(state.person)}…
					</Typography>
				</Stack>
			);
		case "error":
			return (
				<Alert severity="error">
					Could not load details for {formatPersonLabel(state.person)}.
				</Alert>
			);
		case "notFound":
			return (
				<Alert severity="info">
					No details found for {formatPersonLabel(state.person)}.
				</Alert>
			);
		case "success":
			return <PersonDetails details={state.details} />;
	}
}
