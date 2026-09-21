"""Bind generated citation choices to a particular evidence archive.

Example: bound = citation_schema(Draft, source_ids=["S1", "S4"])
The returned model constrains both native generation and response validation.
"""

from copy import deepcopy
from types import GenericAlias
from typing import Annotated, Any, TypeVar, get_args, get_origin

from pydantic import AfterValidator, BaseModel, Field, create_model

Model = TypeVar("Model", bound=BaseModel)


def citation_schema[Model: BaseModel](
    model: type[Model],
    *,
    source_ids: list[str],
    excerpt_ids: list[str] | None = None,
) -> type[Model]:
    """Return an isolated schema with archive-specific citation enums.

    Preserve field bounds, required fields, titles and strictness of the original.
    Empty choices permit empty claim/citation arrays, never invented identities.
    """

    def choice_type(choices: list[str]) -> Any:
        allowed = frozenset(choices)

        def validate(value: str) -> str:
            if value not in allowed:
                raise ValueError("Citation identity is not in the supplied archive")
            return value

        return Annotated[
            str,
            Field(json_schema_extra={"enum": list(dict.fromkeys(choices))}),
            AfterValidator(validate),
        ]

    fields: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        annotation: Any = field.annotation
        bound_field = deepcopy(field)
        if name == "source_ids":
            annotation = GenericAlias(list, choice_type(source_ids))
        elif name == "excerpt_id" and excerpt_ids is not None:
            annotation = choice_type(excerpt_ids)
            bound_field.json_schema_extra = {"enum": list(dict.fromkeys(excerpt_ids))}
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            annotation = citation_schema(
                annotation, source_ids=source_ids, excerpt_ids=excerpt_ids
            )
        elif get_origin(annotation) is list:
            item = get_args(annotation)[0]
            if isinstance(item, type) and issubclass(item, BaseModel):
                annotation = GenericAlias(
                    list,
                    citation_schema(
                        item, source_ids=source_ids, excerpt_ids=excerpt_ids
                    ),
                )
        fields[name] = (annotation, bound_field)
    return create_model(model.__name__, __base__=model, **fields)
