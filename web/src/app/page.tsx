import { redirect } from "next/navigation";

// The role picker at /login lands here once the org portal exists
// (memory_draft.md section 22, step 6). Until then the admin portal is the app.
export default function Home() {
  redirect("/admin");
}
