import { Button, Stack, Typography } from "@mui/material";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import { useMemo } from "react";
import { type Person, people } from "../api";
import type { PersonRef } from "../hooks/usePersonDetails";
import { StatusPill } from "./StatusPill";

type DataTableProps = {
	onViewDetails: (person: PersonRef) => void;
};

// The table stays presentational: it renders rows and emits `onViewDetails(person)`.
// It owns no fetch/UI state, so it remains reusable and the data flow is one-way.
export function DataTable({ onViewDetails }: DataTableProps) {
	// Columns depend on `onViewDetails`; memoize so the grid doesn't rebuild
	// columns on every render (and so a stable callback keeps this stable).
	const columns = useMemo<GridColDef<Person>[]>(
		() => [
			{ field: "id", headerName: "ID", width: 70 },
			{ field: "firstName", headerName: "First name", width: 130 },
			{ field: "lastName", headerName: "Last name", width: 130 },
			{
				field: "age",
				headerName: "Age",
				type: "number",
				width: 90,
			},
			{
				field: "fullName",
				headerName: "Full name",
				description: "This column has a value getter and is not sortable.",
				sortable: false,
				width: 160,
				valueGetter: (_value, row) =>
					`${row.firstName || ""} ${row.lastName || ""}`,
			},
			{
				field: "status",
				headerName: "Status",
				width: 100,
				renderCell: ({ row }) => {
					const temperature = row.temperature;
					const hasTemperature = temperature !== undefined;

					return (
						<Stack
							sx={{
								flexDirection: "row",
								height: "100%",
								alignItems: "center",
								gap: "0.5rem",
							}}
						>
							{/* Task #1: always render the pill; use status "none" (transparent)
							    when there is no temperature so "No Data" lines up with "36.5°C". */}
							<StatusPill
								status={hasTemperature ? getStatus(temperature) : "none"}
							/>
							<Typography variant="body2">
								{getTemperatureText(temperature)}
							</Typography>
						</Stack>
					);
				},
			},
			{
				field: "actions",
				headerName: "Actions",
				width: 140,
				sortable: false,
				renderCell: ({ row }) => (
					<Button
						size="small"
						onClick={() =>
							onViewDetails({
								id: row.id,
								displayName: `${row.firstName} ${row.lastName}`.trim(),
							})
						}
					>
						View details
					</Button>
				),
			},
		],
		[onViewDetails],
	);

	return (
		<DataGrid
			rows={people}
			columns={columns}
			paginationMode="server"
			rowCount={people.length}
			disableRowSelectionOnClick
			disableColumnResize
			disableColumnSelector
			hideFooter
			density="compact"
			disableColumnFilter
			disableColumnSorting
			disableColumnMenu
			disableAutosize
			sx={{
				"&.MuiDataGrid-root": {
					border: "none",
				},
				maxHeight: "24rem",
			}}
		/>
	);
}

function getStatus(temperature: number) {
	if (temperature < 37) return "normal";
	if (temperature <= 38) return "warning";
	return "danger";
}

function getTemperatureText(temperature: number | undefined) {
	if (temperature === undefined) return "No Data";
	return `${temperature.toFixed(1)}°C`;
}
