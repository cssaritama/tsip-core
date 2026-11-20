# Data classification

Version 2.5.0, 20 November 2026. Part of the
[Systems Studio Engineering Standard](PROJECT_STANDARDS.md).

Every file a project creates, receives or publishes belongs to one of four
classes. The class decides where the file may live and who may see it. When a
file could belong to two classes, use the stricter one.

## Classes

| Class | Meaning | Examples |
| --- | --- | --- |
| **Public** | Anyone may read it without harm | Published documentation, open-source code, coursework the course allows to share |
| **Internal** | Useful only to the studio; disclosure causes little harm | Plans, research notes, backlogs, audit reports, unreleased code |
| **Confidential** | Disclosure harms the studio, a client or a partner | Client deliverables, prices, proposals, contracts, unpublished results, strategy |
| **Restricted** | Disclosure causes serious or legal harm, or someone else owns it | Secrets and credentials, personal identifiers, health or immigration records, an employer's or client's systems and data |

## Where each class may live

| Class | Public repository | Private repository | Outside Git |
| --- | --- | --- | --- |
| Public | Yes | Yes | Yes |
| Internal | No | Yes | Yes |
| Confidential | No | Yes, with access limited to the people who need it | Yes, in approved storage |
| Restricted | No | No | Only in encrypted storage the owner of the data approves |

## Handling rules

1. **Secrets never enter Git**, in any repository or in any branch. Use
   environment variables or a secret store, and commit an example file with
   placeholder values. A committed secret is revoked and replaced; deleting the
   commit is not enough.
2. **Data owned by an employer or a client stays in systems that owner
   authorizes.** It is not copied into a personal or studio repository, even
   in private, unless the owner approves it in writing.
3. **Personal data about real people** is collected only when the task needs
   it, kept only as long as it needs it and never published without consent.
4. **Licensed data** keeps its license terms. Record the license next to the
   data or in `REFERENCES.md`. If the license forbids redistribution, commit a
   script that fetches the data instead of the data itself.
5. **Before a repository becomes public**, review its full history, not only
   the latest revision, for any file above the Public class.
6. **Reports and logs** name the file and line where sensitive content appears,
   never the value itself.

## Recording the class

The entry point states the repository's default class. A folder or file that
differs from the default is listed in the entry point with its class and the
reason. Large or Restricted evidence stays in approved storage, and Git records
only its location and integrity hash.
