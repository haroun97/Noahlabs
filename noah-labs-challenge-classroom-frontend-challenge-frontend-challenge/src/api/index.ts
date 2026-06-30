// This file is fake data for the challenge. It is NOT a real server.
// The table and "View details" button use this file instead of calling a backend.

import { faker } from "@faker-js/faker";
import { getRandomInt, sleep } from "../utils";

// One row in the people table.
export type Person = {
	id: number;
	lastName: string;
	firstName: string;
	age: number | null;
	temperature: number | undefined;
};

// Extra info shown when you click "View details" on a person.
export type PersonDetails = {
	personId: number;
	adress: string; // spelling matches the challenge (typo on purpose)
	phone: string;
	email: string;
};

// Pretend to load one person's details from the internet.
// Returns details, or undefined if this person has no details.
// Sometimes throws an error on purpose (like a bad network).
export async function getPersonDetails(
	id: number,
): Promise<PersonDetails | undefined> {
	// Wait a bit so it feels like a slow network (0.5 to 1.5 seconds).
	await sleep(getRandomInt(500, 1500));
	// About half the time, pretend the request failed.
	if (Math.random() < 0.5) throw new Error("Failed to fetch person details");

	return personDetails.find((person) => person.personId === id);
}

// Same seed every time = same fake names and same "who has details" list.
faker.seed(1);
// Make ids 1, 2, 3, ... up to 100.
const ids = Array.from({ length: 100 }, (_, i) => i + 1);
// Build 100 fake people — this is what the table shows.
export const people = ids.map(createRandomPerson);
// Only 80 out of 100 people have extra details (the other 20 → "not found").
const ids_with_details = faker.helpers.shuffle(ids).slice(0, 80);
// Store address, phone, and email for those 80 people.
const personDetails = ids_with_details.map(createRandomPersonDetails);

// Make one fake person for the table (name, age, temperature).
function createRandomPerson(id: number): Person {
	const sex = faker.person.sexType();
	const firstName = faker.person.firstName(sex);
	const lastName = faker.person.lastName();
	const age = faker.number.int({ min: 18, max: 80 });
	const temperature = faker.datatype.boolean({ probability: 0.9 })
		? faker.number.float({ min: 36, max: 39, fractionDigits: 1 })
		: undefined;

	return {
		id,
		firstName,
		lastName,
		age,
		temperature,
	};
}

// Make fake address, phone, and email for one person (the details panel).
function createRandomPersonDetails(personId: number): PersonDetails {
	return {
		personId,
		adress: faker.location.streetAddress(),
		phone: faker.phone.number(),
		email: faker.internet.email(),
	};
}
