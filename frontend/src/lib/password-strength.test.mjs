import assert from "node:assert/strict";
import test from "node:test";
import { checkPassword } from "./password-strength.ts";

test("a password is strong only when every rule passes", () => {
  assert.equal(checkPassword("Str0ng!Passw0rd").strong, true);
  assert.equal(checkPassword("Sh0rt!Pw").strong, false); // under 12 characters
  assert.equal(checkPassword("alllowercase1!").strong, false); // no uppercase
  assert.equal(checkPassword("ALLUPPERCASE1!").strong, false); // no lowercase
  assert.equal(checkPassword("NoNumbersHere!!").strong, false);
  assert.equal(checkPassword("NoSpecials1234").strong, false);
});

test("passed counts each rule met, for the strength bar", () => {
  assert.equal(checkPassword("").passed, 0);
  assert.equal(checkPassword("abc").passed, 1);
  assert.equal(checkPassword("Str0ng!Passw0rd").passed, 5);
});
