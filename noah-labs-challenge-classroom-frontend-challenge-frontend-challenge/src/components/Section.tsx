import { Stack, type StackProps } from "@mui/material";

export function Section({ children, sx, ...props }: StackProps) {
	return (
		<Stack
			sx={{
				padding: "1rem",
				borderRadius: "0.5rem",
				borderWidth: "1px",
				borderStyle: "solid",
				borderColor: "green",
				...sx,
			}}
			{...props}
		>
			{children}
		</Stack>
	);
}
