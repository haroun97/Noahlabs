import { Typography } from "@mui/material";
import type { PersonDetails as PersonDetailsT } from "../api";

export function PersonDetails({
	details,
}: {
	details: PersonDetailsT;
}) {
	return (
		<>
			<Typography>Person ID: {details.personId}</Typography>
			<Typography>Adress: {details.adress}</Typography>
			<Typography>Phone: {details.phone}</Typography>
			<Typography>Email: {details.email}</Typography>
		</>
	);
}
