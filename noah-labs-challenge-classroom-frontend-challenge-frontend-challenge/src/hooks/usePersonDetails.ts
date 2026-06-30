// This hook runs when you click "View details" on a person in the table.
// It loads that person's info and remembers what to show (loading, error, success, etc.).

import { useCallback, useEffect, useRef, useState } from "react";
import { type PersonDetails, getPersonDetails } from "../api";

// Snapshot of who was clicked — captured at interaction time so the panel
// never has to look up row data from a global list (paginated tables, etc.).
export type PersonRef = {
	id: number;
	displayName: string;
};

// All the ways the screen can look after a click.
// We use "status" like a label so we always know which case we are in.
export type PersonDetailsState =
	| { status: "idle" } // nobody clicked yet
	| { status: "loading"; person: PersonRef } // waiting for data...
	| { status: "success"; person: PersonRef; details: PersonDetails } // got the info!
	| { status: "notFound"; person: PersonRef } // this person has no extra info
	| { status: "error"; person: PersonRef }; // something went wrong

// What this hook gives back to App.tsx.
export type UsePersonDetails = {
	state: PersonDetailsState; // what to show in the panel right now
	fetchDetails: (person: PersonRef) => void; // call this when user clicks a row
};

export function usePersonDetails(): UsePersonDetails {
	// Start with "idle" = nothing selected yet.
	const [state, setState] = useState<PersonDetailsState>({ status: "idle" });

	// Counts how many times the user clicked "View details".
	// If you click fast, we only care about the LAST click — not old slow ones.
	// Example: click person 90, then person 2. When 90 finally loads, we ignore it.
	const latestRequestRef = useRef(0);

	// Is the page still open? If user leaves, we stop updating (no errors in console).
	const mountedRef = useRef(true);
	useEffect(() => {
		mountedRef.current = true;
		return () => {
			mountedRef.current = false; // page went away
		};
	}, []);

	// Called when user clicks "View details" on a row.
	const fetchDetails = useCallback((person: PersonRef) => {
		// Give this click a number (1, 2, 3...) so we know if it is still the newest.
		const requestId = ++latestRequestRef.current;

		// Should we throw away the answer? Yes if page closed OR a newer click happened.
		const isStale = () =>
			!mountedRef.current || requestId !== latestRequestRef.current;

		// Show the spinner right away — don't wait for the slow fake network.
		setState({ status: "loading", person });

		// Ask the mock API for this person's details (takes about 0.5 to 1.5 seconds).
		getPersonDetails(person.id)
			.then((details) => {
				if (isStale()) return; // old click — ignore

				if (details) {
					// We got address, phone, email — show them!
					setState({ status: "success", person, details });
				} else {
					// API said "I don't have info for this person."
					setState({ status: "notFound", person });
				}
			})
			.catch(() => {
				if (isStale()) return; // old click — ignore

				// API failed (the mock fails randomly about half the time).
				setState({ status: "error", person });
			});
	}, []);

	// App reads `state` for the panel and passes `fetchDetails` to the table button.
	return { state, fetchDetails };
}
