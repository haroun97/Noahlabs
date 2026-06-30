import { Box, Divider, Stack, Typography } from "@mui/material";
import { DataTable } from "./components/DataTable";
import { PersonDetailsPanel } from "./components/PersonDetailsPanel";
import { Section } from "./components/Section";
import { usePersonDetails } from "./hooks/usePersonDetails";

function App() {
	// Async logic + the race-condition guard live in the hook; App just wires the
	// table's row action to it and hands the resulting state to the panel.
	const { state, fetchDetails } = usePersonDetails();

	return (
		<main
			style={{
				display: "flex",
				flexDirection: "column",
				gap: "1rem",
				padding: "4rem",
			}}
		>
			<Section>
				<Typography variant="h2">
					Welcome to the Noah Labs Frontend Challenge
				</Typography>
				<Typography>
					This challenge was designed to test your frontend skills, where we
					will look into how you solve common UI problems. What matters here is
					not only the final pixels on the screen, but the maintainablity of the
					code and the elegance of the solution. Imagine this is a big project
					with the components being used in many places. Think about how the
					code will evolve over time and the bugs that might arise.
					<ul>
						<li>
							You can only use React primitives, external libraries are not
							allowed.
						</li>
						<li>
							You can use Material UI components for styling if you want to.
						</li>
						<li>The code should be clean and easy to understand.</li>
						<li>It should make good use of typescript for type safety.</li>
						<li>
							The code should be maintainable and avoid fragility, where a local
							change causes unwanted behavior somewhere else.
						</li>
					</ul>
				</Typography>
			</Section>

			<Section>
				<Typography variant="h3">Task #1</Typography>
				<Typography>
					Make the following changes to the code below:
					<ul>
						<li>
							Remove the padding all from the table section, the scroll bar must
							be hugging the right green border.
						</li>
						<li>
							Make sure the "No Data" text is aligned the temperature text.
						</li>
					</ul>
					The section below should look like <em>exactly</em> like this:
				</Typography>
				<img
					src="/table_screenshot.png"
					alt="Screenshot"
					width={"50%"}
					style={{
						border: "1px solid #ccc",
						display: "block",
						margin: "0 auto",
					}}
				/>
			</Section>

			<Section>
				<Typography variant="h3">People</Typography>
				<Typography>Below is a table of people.</Typography>
			</Section>

			{/* Task #1: override padding only for this instance so the scrollbar hugs
			    the green border, without changing Section's shared default. */}
			<Section sx={{ padding: 0 }}>
				<DataTable onViewDetails={fetchDetails} />
			</Section>

			<Section>
				<Typography variant="h3">Task #2</Typography>
				<Typography>
					Add a button to each row of the table that fetches that person's
					details using <code>getPersonDetails</code> in <code>src/api.ts</code>
					and passes it to a <code>PersonDetails</code> placed in the empty
					Section below. Make sure to handle:
					<ul>
						<li>
							Loading state: display something to indicate that the details are
							being loaded.
						</li>
						<li>
							Error state: display a message showing that there was an error.
						</li>
						<li>
							Not found state: display a message showing that the person's
							details were not found.
						</li>
						<li>Success state: display the person's details.</li>
						<li>
							Network effects: network requests may take varying amounts of time
							— what problems could that cause, and how would you guard against
							it?
						</li>
					</ul>
				</Typography>
			</Section>

			<Section>
				<PersonDetailsPanel state={state} />
			</Section>

			<Section>
				<Typography variant="h3">Task #3</Typography>

				<Typography>Please answer the following questions: </Typography>

				<Stack spacing={4}>
					<Box>
						<Typography fontWeight={"bold"} gutterBottom>
							Q1: Can you explain why you chose the styling solution you did for
							task 1 for both table and status pill bar? What would be the other
							alternative way to do them? And why didn’t you choose them?
						</Typography>
						<Typography variant="body1" color="text.secondary" component="div">
							<p>
								<strong>1. Table padding</strong>
							</p>
							<ul>
								<li>
									<strong>What I did:</strong> removed padding on the table's{" "}
									<strong>Section</strong> only:{" "}
									<code>{"<Section sx={{ padding: 0 }}>"}</code>.
								</li>
								<li>
									<strong>Why:</strong> <strong>Section</strong> defaults to{" "}
									<code>padding: 1rem</code>. Overriding it on this one instance
									keeps the fix local; other sections keep their spacing. The
									scrollbar hugs the green border.
								</li>
							</ul>

							<p>
								<strong>2. Status pill / "No Data" alignment</strong>
							</p>
							<ul>
								<li>
									<strong>Problem:</strong> the pill was rendered conditionally
									(<code>{"{row.temperature && <StatusPill/>}"}</code>). Rows
									without a temperature lost the pill's width, so their text
									shifted left.
								</li>
								<li>
									<strong>What I did:</strong> always render{" "}
									<strong>StatusPill</strong> on every row. When there is no
									temperature, I hide the color bar but keep its space, so "No
									Data" aligns with the temperature text.
								</li>
								<li>
									<strong>Result:</strong> the label starts at the same x
									position on every row, "No Data" lines up with the
									temperatures.
								</li>
							</ul>

							<p>
								<strong>3. Alternatives I rejected</strong>
							</p>
							<ul>
								<li>
									<strong>Change shared defaults</strong> in{" "}
									<strong>Section</strong> or <strong>StatusPill</strong>: would
									change those components everywhere else in the app.
								</li>
								<li>
									<strong>Dedicated styled wrapper</strong> just for spacing:
									heavier than a one-line <code>sx</code> override for a single
									instance.
								</li>
								<li>
									<strong>
										Use a placeholder string with spaces (e.g. " "), or
										fixed-width box{" "}
									</strong>{" "}
									instead of the pill. This works, but if the pill size changes,
									the placeholder must be updated manually.
								</li>
							</ul>
						</Typography>
					</Box>

					<Divider />

					<Box>
						<Typography fontWeight={"bold"} gutterBottom>
							Q2: Can you explain how did you manage to satisfy <u>each of</u>{" "}
							the requirements of task 2? How would you have implemented it
							differently if you could use external libraries?
						</Typography>
						<Typography variant="body1" color="text.secondary" component="div">
							<p>I separated the solution into two parts:</p>
							<ul>
								<li>
									<strong>usePersonDetails</strong> manages the request and its
									state.
								</li>
								<li>
									<strong>PersonDetailsPanel</strong> displays the correct
									result.
								</li>
							</ul>

							<p>
								I added a <strong>View details</strong> button to every row.
								When clicked, it passes the person's ID to the request handler
								and calls the provided <strong>getPersonDetails</strong>{" "}
								function.
							</p>

							<p>
								<strong>Requirements</strong>
							</p>
							<ul>
								<li>
									<strong>Loading:</strong> The state changes to{" "}
									<code>loading</code> immediately, and the panel shows a
									spinner and loading message.
								</li>
								<li>
									<strong>Error:</strong> If the request fails, the panel shows
									an error alert.
								</li>
								<li>
									<strong>Not found:</strong> If the API returns{" "}
									<code>undefined</code>, the panel explains that no details
									were found.
								</li>
								<li>
									<strong>Success:</strong> If details are returned, the panel
									renders the existing <strong>PersonDetails</strong> component.
								</li>
								<li>
									<strong>Network effects:</strong> Requests may finish in a
									different order. For example, person A may finish after person
									B even though B was clicked last. Each request receives an
									increasing number, and only the latest request may update the
									UI.
								</li>
								<li>
									<strong>Unmounting:</strong> If the component is removed
									before the request finishes, the late result is ignored.
								</li>
							</ul>

							<p>
								<strong>With external libraries</strong>
							</p>
							<p>
								With external libraries, I would use TanStack Query with the
								person ID as the query key. It would manage loading, errors,
								caching, request deduplication, and separate query state for
								each person.
							</p>
							<p>
								With a real API that supports <strong>AbortSignal</strong>, it
								could also cancel an outdated request. The provided mock
								function cannot be cancelled, so this solution safely ignores
								responses from older requests.
							</p>
						</Typography>
					</Box>

					<Divider />

					<Box>
						<Typography fontWeight={"bold"} gutterBottom>
							Q3: Suppose this was a large scale project, what would have been
							missing in the boilerplate code provided to make it production
							ready?
						</Typography>
						<Typography variant="body1" color="text.secondary" component="div">
							<p>
								For a large-scale production project, the provided boilerplate
								would need several additions:
							</p>
							<ul>
								<li>
									<strong>Real data layer:</strong> A backend API with request
									cancellation, controlled retries, caching, pagination, and
									runtime response validation instead of hardcoded mock data.
								</li>
								<li>
									<strong>Testing:</strong> Unit tests with Vitest and React
									Testing Library, plus integration and end-to-end tests for
									loading, success, error, not-found, and race-condition cases.
								</li>
								<li>
									<strong>Error handling:</strong> Error boundaries for
									rendering failures and a consistent strategy for API and
									unexpected application errors.
								</li>
								<li>
									<strong>Security:</strong> Authentication, authorization,
									secure configuration, and careful handling of personal and
									health-related data.
								</li>
								<li>
									<strong>Observability:</strong> Structured logging, error
									tracking, monitoring, and performance metrics.
								</li>
								<li>
									<strong>Design system:</strong> Shared themes and design
									tokens instead of hardcoded colors, with consistent spacing
									and component styles.
								</li>
								<li>
									<strong>Accessibility:</strong> Accessible names for row
									actions, keyboard navigation, focus handling, status
									announcements, and an accessibility audit of the table.
								</li>
								<li>
									<strong>Internationalization:</strong> Centralized user-facing
									text and i18n support if multiple languages are required.
								</li>
								<li>
									<strong>Tooling and CI:</strong> Automated type checking,
									Biome checks, tests, and production builds on every pull
									request, with environment-based configuration.
								</li>
								<li>
									<strong>Performance:</strong> Pagination or virtualization for
									large datasets, code splitting where useful, and appropriate
									loading placeholders.
								</li>
								<li>
									<strong>Data correctness:</strong> The API field{" "}
									<code>adress</code> should be normalized to{" "}
									<code>address</code> at the data boundary so the UI uses a
									clean internal model.
								</li>
							</ul>
						</Typography>
					</Box>
				</Stack>
			</Section>
		</main>
	);
}

export default App;
