import { Box, type BoxProps } from "@mui/material";

const statusColors = {
	normal: "green",
	warning: "yellow",
	danger: "red",
	// Empty slot for rows with no temperature — keeps width, not a health status.
	none: "transparent",
} as const;

export type StatusLevel = keyof typeof statusColors;

export function StatusPill({
	status,
	sx,
	...props
}: { status: StatusLevel } & BoxProps) {
	return (
		<Box
			aria-hidden={status === "none" ? true : undefined}
			sx={{
				alignItems: "center",
				backgroundColor: statusColors[status],
				borderRadius: "0.25rem",
				width: "0.5rem",
				height: "1.5rem",
				flexShrink: 0,
				...sx,
			}}
			{...props}
		/>
	);
}
